"""
seed_data.py — Populate all clinical content tables for SpeechPath v2.0.

Run from server/:
    python seed_data.py

Idempotent — uses ON CONFLICT DO NOTHING. Safe to re-run.
Requires DATABASE_URL_SYNC in .env (psycopg2 format).
"""
import json
import sys

sys.path.insert(0, ".")
import sqlalchemy as sa
from sqlalchemy import text
from app.config import settings


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _p(pid, display, target=None, instruction="Say this clearly:",
       scope="word", phonemes=None, task_type="articulation",
       pass_msg="Well done!", partial_msg="Good try, keep practicing.",
       fail_msg="Let's try that again.", tc_mode="completion",
       target_wc=None, target_dur=None, min_words=None,
       position="all_positions"):
    return {
        "prompt_id": pid,
        "instruction": instruction,
        "display_content": display,
        "target_response": target or display,
        "eval_scope": scope,
        "speech_target": json.dumps({"target_sounds": phonemes or [], "task_type": task_type}),
        "target_phonemes": json.dumps({"phonemes": phonemes or [], "scope": position}),
        "pass_message": pass_msg,
        "partial_message": partial_msg,
        "fail_message": fail_msg,
        "tc_mode": tc_mode,
        "target_word_count": target_wc,
        "target_duration_sec": target_dur,
        "min_length_words": min_words,
    }


def _lvl(lid, task_id, name, score, prompts):
    return {"level_id": lid, "task_id": task_id,
            "level_name": name, "difficulty_score": score, "prompts": prompts}


def _dm(task_id, *defect_ids, level="primary"):
    return [{"defect_id": d, "relevance_level": level} for d in defect_ids]


# ─── WPM CONFIG ───────────────────────────────────────────────────────────────

WPM_CONFIG = {
    "phoneme":      {"ideal_wpm_min": 40,  "ideal_wpm_max": 70,  "wpm_tolerance": 15},
    "word":         {"ideal_wpm_min": 60,  "ideal_wpm_max": 90,  "wpm_tolerance": 20},
    "sentence":     {"ideal_wpm_min": 90,  "ideal_wpm_max": 130, "wpm_tolerance": 25},
    "spontaneous":  {"ideal_wpm_min": 80,  "ideal_wpm_max": 120, "wpm_tolerance": 20},
    "fluency":      {"ideal_wpm_min": 40,  "ideal_wpm_max": 80,  "wpm_tolerance": 15},
    "conversation": {"ideal_wpm_min": 80,  "ideal_wpm_max": 120, "wpm_tolerance": 20},
}

# ─── SCORING WEIGHTS ──────────────────────────────────────────────────────────

SCORING_WEIGHTS = {
    "articulation_phoneme":  {"pa": 0.55, "wa": 0.20, "fs": 0.10, "srs": 0.10, "cs": 0.05},
    "articulation_sentence": {"pa": 0.30, "wa": 0.35, "fs": 0.20, "srs": 0.10, "cs": 0.05},
    "fluency":               {"pa": 0.20, "wa": 0.20, "fs": 0.45, "srs": 0.10, "cs": 0.05},
    "language":              {"pa": 0.25, "wa": 0.45, "fs": 0.15, "srs": 0.10, "cs": 0.05},
    "voice":                 {"pa": 0.20, "wa": 0.25, "fs": 0.20, "srs": 0.15, "cs": 0.20},
    "motor_speech":          {"pa": 0.45, "wa": 0.20, "fs": 0.15, "srs": 0.15, "cs": 0.05},
    "social_communication":  {"pa": 0.20, "wa": 0.30, "fs": 0.20, "srs": 0.10, "cs": 0.20},
}

for _c, _w in SCORING_WEIGHTS.items():
    assert abs(sum(_w.values()) - 1.0) < 0.001, f"{_c} weights != 1.0"


# ─── DEFECTS (30) ─────────────────────────────────────────────────────────────

DEFECTS = [
    {"defect_id": "defect_phono_child",    "code": "PHONO_CH",    "category": "articulation",        "age_group": "child",
     "name": "Phonological Disorder",
     "description": "Patterns of sound errors affecting the phonological system — substitutions, omissions, and assimilations across multiple phoneme classes."},
    {"defect_id": "defect_lisp_child",     "code": "LISP_CH",     "category": "articulation",        "age_group": "child",
     "name": "Lisping — Sibilant Distortion (/s/, /z/)",
     "description": "Distortion of sibilant phonemes /s/ and /z/, presenting as interdental or lateral lisp."},
    {"defect_id": "defect_rhot_child",     "code": "RHOT_CH",     "category": "articulation",        "age_group": "child",
     "name": "Rhotacism — /r/ Sound Distortion",
     "description": "Difficulty producing the /r/ phoneme; substitution or distortion common in children ages 5–8."},
    {"defect_id": "defect_front_child",    "code": "FRONT_CH",    "category": "articulation",        "age_group": "child",
     "name": "Fronting — Velar Substitution (/k/→/t/, /g/→/d/)",
     "description": "Phonological process where velars /k/ and /g/ are replaced by alveolars /t/ and /d/."},
    {"defect_id": "defect_clust_child",    "code": "CLUST_CH",    "category": "articulation",        "age_group": "child",
     "name": "Consonant Cluster Reduction",
     "description": "Simplification of consonant clusters by omitting elements (e.g., 'stop'→'top', 'play'→'pay')."},
    {"defect_id": "defect_devstut_child",  "code": "DEVSTUT_CH",  "category": "fluency",             "age_group": "child",
     "name": "Developmental Stuttering",
     "description": "Childhood-onset fluency disorder with repetitions, prolongations, and blocks; may include secondary behaviours."},
    {"defect_id": "defect_clutter_child",  "code": "CLUT_CH",     "category": "fluency",             "age_group": "child",
     "name": "Cluttering",
     "description": "Excessively fast or irregular speech rate with collapsed syllables and reduced intelligibility."},
    {"defect_id": "defect_exprlang_child", "code": "EXPRLANG_CH", "category": "language",            "age_group": "child",
     "name": "Expressive Language Disorder",
     "description": "Difficulty formulating language; limited vocabulary, sentence structure errors, and word-finding difficulties."},
    {"defect_id": "defect_reclang_child",  "code": "RECLANG_CH",  "category": "language",            "age_group": "child",
     "name": "Receptive Language Disorder",
     "description": "Difficulty understanding spoken language; problems following directions and processing complex sentences."},
    {"defect_id": "defect_latelang_child", "code": "LATELANG_CH", "category": "language",            "age_group": "child",
     "name": "Late Language Emergence",
     "description": "Delayed onset of first words and phrases in toddlers with no other identified developmental delay."},
    {"defect_id": "defect_vocnod_child",   "code": "VOCNOD_CH",   "category": "voice",               "age_group": "child",
     "name": "Vocal Nodules — Hoarseness",
     "description": "Bilateral vocal fold lesions causing hoarseness, reduced pitch range, and vocal fatigue in children."},
    {"defect_id": "defect_reson_child",    "code": "RESON_CH",    "category": "voice",               "age_group": "child",
     "name": "Resonance Disorder — Hypernasality",
     "description": "Excessive nasal resonance; often associated with velopharyngeal insufficiency or cleft palate."},
    {"defect_id": "defect_cas_child",      "code": "CAS_CH",      "category": "motor_speech",        "age_group": "child",
     "name": "Childhood Apraxia of Speech (CAS)",
     "description": "Motor speech disorder with inconsistent errors, difficulty sequencing motor plans, and prosodic abnormalities."},
    {"defect_id": "defect_asd_child",      "code": "ASD_CH",      "category": "social_communication","age_group": "child",
     "name": "ASD — Social Communication Profile",
     "description": "Social communication and interaction difficulties associated with ASD; pragmatic language challenges, reduced joint attention."},
    {"defect_id": "defect_mute_child",     "code": "MUTE_CH",     "category": "social_communication","age_group": "child",
     "name": "Selective Mutism",
     "description": "Consistent failure to speak in specific social situations despite speaking in others; anxiety-based presentation."},
    {"defect_id": "defect_dysart_adult",   "code": "DYSART_AD",   "category": "articulation",        "age_group": "adult",
     "name": "Dysarthric Articulation — Acquired",
     "description": "Motor speech disorder from neurological damage; imprecise consonants, distorted vowels, reduced intelligibility."},
    {"defect_id": "defect_lisp_adult",     "code": "LISP_AD",     "category": "articulation",        "age_group": "adult",
     "name": "Lisping — Sibilant Distortion (persisting)",
     "description": "Persisting or acquired sibilant distortion in adults; established incorrect motor plans require repatterning."},
    {"defect_id": "defect_rhot_adult",     "code": "RHOT_AD",     "category": "articulation",        "age_group": "adult",
     "name": "Rhotacism — /r/ Distortion (post-neurological)",
     "description": "Post-neurological /r/ distortion following stroke or TBI; requires motor re-establishment."},
    {"defect_id": "defect_neurstut_adult", "code": "NEURSTUT_AD", "category": "fluency",             "age_group": "adult",
     "name": "Neurogenic Stuttering — Acquired",
     "description": "Acquired stuttering following neurological event; different profile from developmental stuttering."},
    {"defect_id": "defect_clutter_adult",  "code": "CLUT_AD",     "category": "fluency",             "age_group": "adult",
     "name": "Cluttering",
     "description": "Adult-presenting cluttering with rapid irregular rate; may co-occur with ADHD."},
    {"defect_id": "defect_psychdis_adult", "code": "PSYDIS_AD",   "category": "fluency",             "age_group": "adult",
     "name": "Psychogenic Disfluency",
     "description": "Fluency disorder with psychological aetiology; variable presentation, sudden onset, heightened anxiety."},
    {"defect_id": "defect_aphexpr_adult",  "code": "APHEXPR_AD",  "category": "language",            "age_group": "adult",
     "name": "Aphasia — Expressive (Broca's)",
     "description": "Non-fluent aphasia with effortful speech, reduced phrase length, agrammatism, preserved comprehension."},
    {"defect_id": "defect_aphrec_adult",   "code": "APHREC_AD",   "category": "language",            "age_group": "adult",
     "name": "Aphasia — Receptive (Wernicke's)",
     "description": "Fluent aphasia with impaired comprehension, paraphasias, and reduced error awareness."},
    {"defect_id": "defect_anomia_adult",   "code": "ANOMIA_AD",   "category": "language",            "age_group": "adult",
     "name": "Anomia — Word Finding Difficulty",
     "description": "Predominant word retrieval deficit with tip-of-tongue states, circumlocutions, and paraphasias."},
    {"defect_id": "defect_vocnod_adult",   "code": "VOCNOD_AD",   "category": "voice",               "age_group": "adult",
     "name": "Vocal Nodules — Hoarseness",
     "description": "Bilateral vocal fold nodules in adults; hoarseness, breathiness, reduced pitch range."},
    {"defect_id": "defect_vcpar_adult",    "code": "VCPAR_AD",    "category": "voice",               "age_group": "adult",
     "name": "Vocal Cord Paralysis",
     "description": "Unilateral or bilateral vocal fold paralysis; breathy voice, reduced loudness, aspiration risk."},
    {"defect_id": "defect_spasdys_adult",  "code": "SPASDYS_AD",  "category": "voice",               "age_group": "adult",
     "name": "Spasmodic Dysphonia",
     "description": "Focal laryngeal dystonia causing spasmodic voice breaks; adductor or abductor type."},
    {"defect_id": "defect_aos_adult",      "code": "AOS_AD",      "category": "motor_speech",        "age_group": "adult",
     "name": "Acquired Apraxia of Speech (AOS)",
     "description": "Acquired motor speech disorder with inconsistent articulatory errors and effortful speech."},
    {"defect_id": "defect_hypodys_adult",  "code": "HYPODYS_AD",  "category": "motor_speech",        "age_group": "adult",
     "name": "Hypokinetic Dysarthria — Parkinson's",
     "description": "Parkinson's-associated dysarthria; hypophonia, monopitch, monoloudness, festinating rate."},
    {"defect_id": "defect_spastdys_adult", "code": "SPASTDYS_AD", "category": "motor_speech",        "age_group": "adult",
     "name": "Spastic Dysarthria — Post-Stroke",
     "description": "Post-stroke spastic dysarthria; harsh voice, slow rate, imprecise articulation, hypernasality."},
]

assert len(DEFECTS) == 30, f"Expected 30 defects, got {len(DEFECTS)}"


# ─── EMOTION WEIGHTS (2) ──────────────────────────────────────────────────────

EMOTION_WEIGHTS = [
    {"config_id": "ewc_child", "age_group": "child",
     "w_happy": 0.25, "w_excited": 0.20, "w_neutral": 0.15, "w_surprised": 0.10,
     "w_sad": 0.05,  "w_angry": 0.00,   "w_fearful": 0.05, "w_positive_affect": 0.15,
     "w_focused": 0.05, "version": 1},
    {"config_id": "ewc_adult", "age_group": "adult",
     "w_happy": 0.15, "w_excited": 0.10, "w_neutral": 0.20, "w_surprised": 0.05,
     "w_sad": 0.05,  "w_angry": 0.00,   "w_fearful": 0.05, "w_positive_affect": 0.15,
     "w_focused": 0.25, "version": 1},
]


# ─── PA THRESHOLDS (30) ───────────────────────────────────────────────────────

PA_THRESHOLDS = [
    {"threshold_id": "pat_phono_child",    "defect_id": "defect_phono_child",    "min_pa_to_pass": 65.0, "target_phonemes": None,               "phoneme_scope": "multiple",   "severity_modifier": 1.0, "notes": "Multiple error phonemes; lower threshold."},
    {"threshold_id": "pat_lisp_child",     "defect_id": "defect_lisp_child",     "min_pa_to_pass": 70.0, "target_phonemes": ["/s/", "/z/"],      "phoneme_scope": "all_positions","severity_modifier": 1.0, "notes": "Single phoneme class; 70% predicts generalisation."},
    {"threshold_id": "pat_rhot_child",     "defect_id": "defect_rhot_child",     "min_pa_to_pass": 70.0, "target_phonemes": ["/r/"],             "phoneme_scope": "all_positions","severity_modifier": 1.0, "notes": "Single phoneme target."},
    {"threshold_id": "pat_front_child",    "defect_id": "defect_front_child",    "min_pa_to_pass": 72.0, "target_phonemes": ["/k/", "/g/"],      "phoneme_scope": "all_positions","severity_modifier": 1.0, "notes": "Two velars; slightly higher threshold."},
    {"threshold_id": "pat_clust_child",    "defect_id": "defect_clust_child",    "min_pa_to_pass": 65.0, "target_phonemes": None,               "phoneme_scope": "cluster",    "severity_modifier": 1.0, "notes": "Clusters harder; lower threshold."},
    {"threshold_id": "pat_devstut_child",  "defect_id": "defect_devstut_child",  "min_pa_to_pass": 50.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "PA secondary; fluency dominates."},
    {"threshold_id": "pat_clutter_child",  "defect_id": "defect_clutter_child",  "min_pa_to_pass": 55.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "PA secondary; rate dominates."},
    {"threshold_id": "pat_exprlang_child", "defect_id": "defect_exprlang_child", "min_pa_to_pass": 60.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "WA dominates."},
    {"threshold_id": "pat_reclang_child",  "defect_id": "defect_reclang_child",  "min_pa_to_pass": 60.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "WA dominates."},
    {"threshold_id": "pat_latelang_child", "defect_id": "defect_latelang_child", "min_pa_to_pass": 55.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Emerging language; more lenient."},
    {"threshold_id": "pat_vocnod_child",   "defect_id": "defect_vocnod_child",   "min_pa_to_pass": 45.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Voice quality primary; PA low priority."},
    {"threshold_id": "pat_reson_child",    "defect_id": "defect_reson_child",    "min_pa_to_pass": 65.0, "target_phonemes": ["/p/","/b/","/t/","/d/","/k/"], "phoneme_scope": "oral_pressure", "severity_modifier": 1.0, "notes": "Oral consonant pressure is metric."},
    {"threshold_id": "pat_cas_child",      "defect_id": "defect_cas_child",      "min_pa_to_pass": 60.0, "target_phonemes": None,               "phoneme_scope": "task_specific","severity_modifier": 1.0, "notes": "Motor inconsistency is key measure."},
    {"threshold_id": "pat_asd_child",      "defect_id": "defect_asd_child",      "min_pa_to_pass": 50.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Social comm; PA not primary."},
    {"threshold_id": "pat_mute_child",     "defect_id": "defect_mute_child",     "min_pa_to_pass": 40.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Any vocalisation is the therapeutic goal."},
    {"threshold_id": "pat_dysart_adult",   "defect_id": "defect_dysart_adult",   "min_pa_to_pass": 60.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Articulatory precision."},
    {"threshold_id": "pat_lisp_adult",     "defect_id": "defect_lisp_adult",     "min_pa_to_pass": 72.0, "target_phonemes": ["/s/", "/z/"],      "phoneme_scope": "all_positions","severity_modifier": 1.0, "notes": "Established adult motor pattern; higher standard."},
    {"threshold_id": "pat_rhot_adult",     "defect_id": "defect_rhot_adult",     "min_pa_to_pass": 70.0, "target_phonemes": ["/r/"],             "phoneme_scope": "all_positions","severity_modifier": 1.0, "notes": "Post-neurological; same baseline as child."},
    {"threshold_id": "pat_neurstut_adult", "defect_id": "defect_neurstut_adult", "min_pa_to_pass": 50.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Fluency dominates."},
    {"threshold_id": "pat_clutter_adult",  "defect_id": "defect_clutter_adult",  "min_pa_to_pass": 55.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Rate dominates."},
    {"threshold_id": "pat_psychdis_adult", "defect_id": "defect_psychdis_adult", "min_pa_to_pass": 50.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Fluency + engagement."},
    {"threshold_id": "pat_aphexpr_adult",  "defect_id": "defect_aphexpr_adult",  "min_pa_to_pass": 55.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "WA + word retrieval matter more."},
    {"threshold_id": "pat_aphrec_adult",   "defect_id": "defect_aphrec_adult",   "min_pa_to_pass": 50.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Comprehension task; PA secondary."},
    {"threshold_id": "pat_anomia_adult",   "defect_id": "defect_anomia_adult",   "min_pa_to_pass": 60.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Word retrieval; WA dominates."},
    {"threshold_id": "pat_vocnod_adult",   "defect_id": "defect_vocnod_adult",   "min_pa_to_pass": 45.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Voice quality primary."},
    {"threshold_id": "pat_vcpar_adult",    "defect_id": "defect_vcpar_adult",    "min_pa_to_pass": 45.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Voice quality primary."},
    {"threshold_id": "pat_spasdys_adult",  "defect_id": "defect_spasdys_adult",  "min_pa_to_pass": 45.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Voice quality primary."},
    {"threshold_id": "pat_aos_adult",      "defect_id": "defect_aos_adult",      "min_pa_to_pass": 62.0, "target_phonemes": None,               "phoneme_scope": "task_specific","severity_modifier": 1.0, "notes": "Motor relearning; PA important."},
    {"threshold_id": "pat_hypodys_adult",  "defect_id": "defect_hypodys_adult",  "min_pa_to_pass": 55.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Loudness + rate primary."},
    {"threshold_id": "pat_spastdys_adult", "defect_id": "defect_spastdys_adult", "min_pa_to_pass": 58.0, "target_phonemes": None,               "phoneme_scope": None,         "severity_modifier": 1.0, "notes": "Precision over rate."},
]

assert len(PA_THRESHOLDS) == 30, f"Expected 30 PA thresholds, got {len(PA_THRESHOLDS)}"


# ─── TASKS ────────────────────────────────────────────────────────────────────

TASKS = [

    # ══════════════════════════════════════════════════════════════════════════
    # ARTICULATION — SHARED TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_word_level_artic",
        "name": "Word-level articulation drill",
        "type": "articulation", "task_mode": "repeat",
        "description": "Target phoneme production in initial, medial, and final word positions.",
        "wpm_category": "word", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA is primary — targets word-position accuracy",
        "defect_mappings": _dm("task_word_level_artic",
            "defect_phono_child","defect_lisp_child","defect_rhot_child",
            "defect_front_child","defect_clust_child","defect_cas_child",
            "defect_dysart_adult","defect_lisp_adult","defect_rhot_adult","defect_aos_adult"),
        "levels": [
            _lvl("lvl_wla_beg","task_word_level_artic","beginner",1,[
                _p("p_wla_beg_01","sun","sun","Say this word clearly:",scope="word",position="word_initial"),
                _p("p_wla_beg_02","bus","bus","Say this word clearly:",scope="word",position="word_final"),
                _p("p_wla_beg_03","cup","cup","Say this word clearly:",scope="word",position="word_initial"),
            ]),
            _lvl("lvl_wla_int","task_word_level_artic","intermediate",2,[
                _p("p_wla_int_01","sister","sister","Say this word clearly:",scope="word"),
                _p("p_wla_int_02","scissors","scissors","Say this word carefully:",scope="word"),
                _p("p_wla_int_03","glasses","glasses","Say each sound clearly:",scope="word"),
            ]),
            _lvl("lvl_wla_adv","task_word_level_artic","advanced",3,[
                _p("p_wla_adv_01","red river","red river","Say these words clearly:",scope="word",
                   pass_msg="Excellent clarity!"),
                _p("p_wla_adv_02","big black bag","big black bag","Say the phrase clearly:",scope="sentence"),
                _p("p_wla_adv_03","six silly seals","six silly seals","Read this phrase aloud:",scope="sentence"),
            ]),
        ],
    },

    {
        "task_id": "task_phoneme_carrier",
        "name": "Carrier phrase drill",
        "type": "articulation", "task_mode": "repeat",
        "description": "Target phoneme embedded in carrier phrases to support contextual production.",
        "wpm_category": "word", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA is primary in target word within carrier phrase",
        "defect_mappings": _dm("task_phoneme_carrier",
            "defect_phono_child","defect_lisp_child","defect_rhot_child",
            "defect_front_child","defect_clust_child","defect_cas_child"),
        "levels": [
            _lvl("lvl_pca_beg","task_phoneme_carrier","beginner",1,[
                _p("p_pca_beg_01","I see a sun.","I see a sun.","Repeat the phrase:",scope="sentence"),
                _p("p_pca_beg_02","I see a cat.","I see a cat.","Repeat the phrase:",scope="sentence"),
                _p("p_pca_beg_03","I see a cup.","I see a cup.","Repeat the phrase:",scope="sentence"),
            ]),
            _lvl("lvl_pca_int","task_phoneme_carrier","intermediate",2,[
                _p("p_pca_int_01","I can say sister clearly.","I can say sister clearly.","Repeat:",scope="sentence"),
                _p("p_pca_int_02","I can say river clearly.","I can say river clearly.","Repeat:",scope="sentence"),
                _p("p_pca_int_03","I can say kitchen clearly.","I can say kitchen clearly.","Repeat:",scope="sentence"),
            ]),
            _lvl("lvl_pca_adv","task_phoneme_carrier","advanced",3,[
                _p("p_pca_adv_01","I want to say it slowly and clearly.","I want to say it slowly and clearly.","Repeat the sentence:",scope="sentence"),
                _p("p_pca_adv_02","The scissors are on the table.","The scissors are on the table.","Read and repeat:",scope="sentence"),
                _p("p_pca_adv_03","She sells seashells by the seashore.","She sells seashells by the seashore.","Repeat carefully:",scope="sentence"),
            ]),
        ],
    },

    {
        "task_id": "task_phoneme_sentences",
        "name": "Phoneme-dense sentence reading",
        "type": "articulation", "task_mode": "read_aloud",
        "description": "Read sentences designed to maximise occurrence of target phonemes across positions.",
        "wpm_category": "sentence", "weight_category": "articulation_sentence",
        "scoring_notes": "WA and PA both important across sentence context",
        "defect_mappings": _dm("task_phoneme_sentences",
            "defect_phono_child","defect_lisp_child","defect_front_child",
            "defect_clust_child","defect_reson_child"),
        "levels": [
            _lvl("lvl_pse_beg","task_phoneme_sentences","beginner",1,[
                _p("p_pse_beg_01","Sam sits.","Sam sits.","Read aloud:",scope="sentence"),
                _p("p_pse_beg_02","Cats can run.","Cats can run.","Read aloud:",scope="sentence"),
                _p("p_pse_beg_03","The sun is big.","The sun is big.","Read aloud:",scope="sentence"),
            ]),
            _lvl("lvl_pse_int","task_phoneme_sentences","intermediate",2,[
                _p("p_pse_int_01","Sally saw six small cats.","Sally saw six small cats.","Read the sentence:",scope="sentence"),
                _p("p_pse_int_02","The silly snake slid slowly.","The silly snake slid slowly.","Read aloud clearly:",scope="sentence"),
                _p("p_pse_int_03","Kevin kept kicking the ball.","Kevin kept kicking the ball.","Read aloud:",scope="sentence"),
            ]),
            _lvl("lvl_pse_adv","task_phoneme_sentences","advanced",3,[
                _p("p_pse_adv_01","Susan saw six Swiss wristwatches.","Susan saw six Swiss wristwatches.","Read at a comfortable pace:",scope="sentence"),
                _p("p_pse_adv_02","She sells seashells by the seashore.","She sells seashells by the seashore.","Read clearly:",scope="sentence"),
                _p("p_pse_adv_03","Crisp crossing creates clear constant contrast.","Crisp crossing creates clear constant contrast.","Read aloud:",scope="sentence"),
            ]),
        ],
    },

    {
        "task_id": "task_minimal_pairs",
        "name": "Minimal pairs contrast drill",
        "type": "articulation", "task_mode": "repeat",
        "description": "Produce minimal pair word contrasts to heighten phonemic awareness and accuracy.",
        "wpm_category": "word", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA critical for distinguishing target phoneme from substituted phoneme",
        "defect_mappings": _dm("task_minimal_pairs",
            "defect_phono_child","defect_rhot_child","defect_front_child","defect_clust_child"),
        "levels": [
            _lvl("lvl_mip_beg","task_minimal_pairs","beginner",1,[
                _p("p_mip_beg_01","tea — key","tea — key","Say both words:",scope="word"),
                _p("p_mip_beg_02","day — gay","day — gay","Say both words:",scope="word"),
                _p("p_mip_beg_03","toe — go","toe — go","Say both words:",scope="word"),
            ]),
            _lvl("lvl_mip_int","task_minimal_pairs","intermediate",2,[
                _p("p_mip_int_01","run — won","run — won","Say both words clearly:",scope="word"),
                _p("p_mip_int_02","play — pay","play — pay","Say both words:",scope="word"),
                _p("p_mip_int_03","sip — zip","sip — zip","Say both words:",scope="word"),
            ]),
            _lvl("lvl_mip_adv","task_minimal_pairs","advanced",3,[
                _p("p_mip_adv_01","rate — late — gate","rate — late — gate","Say all three words:",scope="word"),
                _p("p_mip_adv_02","stop — top — pop","stop — top — pop","Say each word clearly:",scope="word"),
                _p("p_mip_adv_03","spin — pin — bin","spin — pin — bin","Say each word:",scope="word"),
            ]),
        ],
    },

    {
        "task_id": "task_spont_speech_artic",
        "name": "Spontaneous speech — articulation monitoring",
        "type": "articulation", "task_mode": "describe",
        "description": "Describe a picture or topic while monitoring articulatory accuracy.",
        "wpm_category": "spontaneous", "weight_category": "articulation_sentence",
        "scoring_notes": "WA and FS measure naturalness; PA monitors target phonemes in connected speech",
        "defect_mappings": _dm("task_spont_speech_artic",
            "defect_phono_child","defect_lisp_child","defect_rhot_child","defect_front_child",
            "defect_clust_child","defect_clutter_child","defect_lisp_adult",
            "defect_rhot_adult","defect_clutter_adult"),
        "levels": [
            _lvl("lvl_ssa_beg","task_spont_speech_artic","beginner",1,[
                _p("p_ssa_beg_01","What do you see? Say two things you notice.",None,
                   "Look at the picture. Describe what you see:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=10,min_words=5),
                _p("p_ssa_beg_02","What is the boy doing?",None,
                   "Answer the question in one or two sentences:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=12,min_words=5),
                _p("p_ssa_beg_03","Tell me about your favourite animal.",None,
                   "Talk about your favourite animal:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=15,min_words=8),
            ]),
            _lvl("lvl_ssa_int","task_spont_speech_artic","intermediate",2,[
                _p("p_ssa_int_01","Describe what is happening in this picture.",None,
                   "Describe the picture in at least 3 sentences:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=25,min_words=15),
                _p("p_ssa_int_02","Tell me about your school day.",None,
                   "Talk about your day at school:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=25,min_words=15),
                _p("p_ssa_int_03","What would you do on a rainy day?",None,
                   "Answer the question in full sentences:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=25,min_words=15),
            ]),
            _lvl("lvl_ssa_adv","task_spont_speech_artic","advanced",3,[
                _p("p_ssa_adv_01","Tell me a short story about a child at the park.",None,
                   "Tell a short story in 4-5 sentences:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=50,min_words=30),
                _p("p_ssa_adv_02","Describe your best memory.",None,
                   "Talk about your best memory — try to use clear speech throughout:",
                   scope="discourse",task_type="spontaneous",tc_mode="duration",target_dur=30,min_words=30),
                _p("p_ssa_adv_03","Explain how to make a sandwich.",None,
                   "Explain the steps clearly:",scope="discourse",
                   task_type="spontaneous",tc_mode="word_count",target_wc=50,min_words=30),
            ]),
        ],
    },

    {
        "task_id": "task_oral_motor_exercise",
        "name": "Oral motor exercise sequence",
        "type": "articulation", "task_mode": "imitate",
        "description": "Structured oral motor exercises targeting lip rounding, tongue elevation, and jaw movement.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA measures precision of oro-motor movements via sibilant accuracy",
        "defect_mappings": _dm("task_oral_motor_exercise",
            "defect_lisp_child","defect_reson_child","defect_dysart_adult",
            "defect_lisp_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_ome_beg","task_oral_motor_exercise","beginner",1,[
                _p("p_ome_beg_01","ooo — eee — ooo","ooo — eee — ooo","Imitate the lip movements:",scope="phoneme",phonemes=["/uː/","/iː/"]),
                _p("p_ome_beg_02","la la la la la","la la la la la","Imitate the tongue movement:",scope="phoneme",phonemes=["/l/"]),
                _p("p_ome_beg_03","pa pa pa","pa pa pa","Imitate clearly:",scope="phoneme",phonemes=["/p/"]),
            ]),
            _lvl("lvl_ome_int","task_oral_motor_exercise","intermediate",2,[
                _p("p_ome_int_01","ta — da — na — ta — da — na","ta — da — na — ta — da — na","Imitate the sequence:",scope="phoneme"),
                _p("p_ome_int_02","sss — zzz — sss — zzz","sss — zzz — sss — zzz","Hold each sound for 2 seconds:",scope="phoneme",phonemes=["/s/","/z/"]),
                _p("p_ome_int_03","ka — ga — ka — ga","ka — ga — ka — ga","Imitate clearly:",scope="phoneme",phonemes=["/k/","/g/"]),
            ]),
            _lvl("lvl_ome_adv","task_oral_motor_exercise","advanced",3,[
                _p("p_ome_adv_01","pa — ta — ka — pa — ta — ka","pa — ta — ka — pa — ta — ka","Say the sequence at a steady pace:",scope="phoneme"),
                _p("p_ome_adv_02","la — sa — za — la — sa — za","la — sa — za — la — sa — za","Imitate with clear tongue placement:",scope="phoneme"),
                _p("p_ome_adv_03","ma — na — nga — ma — na — nga","ma — na — nga — ma — na — nga","Imitate the sequence:",scope="phoneme"),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # ARTICULATION — DEFECT-SPECIFIC TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_isolated_phoneme_phono",
        "name": "Isolated phoneme — broad inventory (phonological)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Isolation and syllable production across a broad phoneme inventory for phonological disorder.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA is the primary metric; each target phoneme scored independently",
        "defect_mappings": _dm("task_isolated_phoneme_phono","defect_phono_child"),
        "levels": [
            _lvl("lvl_ipp_beg","task_isolated_phoneme_phono","beginner",1,[
                _p("p_ipp_beg_01","p  b  m","p  b  m","Say each sound clearly:",scope="phoneme",phonemes=["/p/","/b/","/m/"]),
                _p("p_ipp_beg_02","t  d  n","t  d  n","Say each sound clearly:",scope="phoneme",phonemes=["/t/","/d/","/n/"]),
                _p("p_ipp_beg_03","f  v  s","f  v  s","Say each sound clearly:",scope="phoneme",phonemes=["/f/","/v/","/s/"]),
            ]),
            _lvl("lvl_ipp_int","task_isolated_phoneme_phono","intermediate",2,[
                _p("p_ipp_int_01","pa  ba  ma","pa  ba  ma","Say each syllable clearly:",scope="phoneme",phonemes=["/p/","/b/","/m/"]),
                _p("p_ipp_int_02","ta  da  na","ta  da  na","Say each syllable:",scope="phoneme",phonemes=["/t/","/d/","/n/"]),
                _p("p_ipp_int_03","fa  va  sa","fa  va  sa","Say each syllable:",scope="phoneme",phonemes=["/f/","/v/","/s/"]),
            ]),
            _lvl("lvl_ipp_adv","task_isolated_phoneme_phono","advanced",3,[
                _p("p_ipp_adv_01","pin — bin — tin — din","pin — bin — tin — din","Say each word clearly:",scope="word",phonemes=["/p/","/b/","/t/","/d/"]),
                _p("p_ipp_adv_02","fan — van — can — man","fan — van — can — man","Say each word:",scope="word",phonemes=["/f/","/v/","/k/","/m/"]),
                _p("p_ipp_adv_03","sit — zip — fit — bit","sit — zip — fit — bit","Say each word clearly:",scope="word",phonemes=["/s/","/z/","/f/","/b/"]),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_sz_child",
        "name": "Isolated phoneme — /s/ and /z/ (child lisp)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Isolation and syllable production targeting /s/ and /z/ for child lisping.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on /s/ and /z/ is primary; tongue tip placement is key",
        "defect_mappings": _dm("task_isolated_phoneme_sz_child","defect_lisp_child"),
        "levels": [
            _lvl("lvl_szc_beg","task_isolated_phoneme_sz_child","beginner",1,[
                _p("p_szc_beg_01","s","s","Hold the /s/ sound for 3 seconds:",scope="phoneme",phonemes=["/s/"],position="isolation"),
                _p("p_szc_beg_02","z","z","Hold the /z/ sound for 3 seconds:",scope="phoneme",phonemes=["/z/"],position="isolation"),
                _p("p_szc_beg_03","sa  sa  sa","sa  sa  sa","Repeat the syllable:",scope="phoneme",phonemes=["/s/"],position="cv_syllable"),
            ]),
            _lvl("lvl_szc_int","task_isolated_phoneme_sz_child","intermediate",2,[
                _p("p_szc_int_01","si  su  se","si  su  se","Say each syllable:",scope="phoneme",phonemes=["/s/"],position="cv_syllable"),
                _p("p_szc_int_02","za  zi  zu","za  zi  zu","Say each syllable:",scope="phoneme",phonemes=["/z/"],position="cv_syllable"),
                _p("p_szc_int_03","as  is  us","as  is  us","Say each syllable — focus on final /s/:",scope="phoneme",phonemes=["/s/"],position="vc_syllable"),
            ]),
            _lvl("lvl_szc_adv","task_isolated_phoneme_sz_child","advanced",3,[
                _p("p_szc_adv_01","sun  sit  sock","sun  sit  sock","Say each word — /s/ at the start:",scope="word",phonemes=["/s/"],position="word_initial"),
                _p("p_szc_adv_02","bus  mess  glass","bus  mess  glass","Say each word — /s/ at the end:",scope="word",phonemes=["/s/"],position="word_final"),
                _p("p_szc_adv_03","sa si su  as is  sun bus sister","sa si su  as is  sun bus sister","Say the full sequence:",scope="word",phonemes=["/s/","/z/"],position="mixed_sequence"),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_r_child",
        "name": "Isolated phoneme — /r/ (child rhotacism)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Isolation, rhotic syllables, and word production targeting /r/ for child rhotacism.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on /r/ is primary; bunching vs retroflex both acceptable",
        "defect_mappings": _dm("task_isolated_phoneme_r_child","defect_rhot_child"),
        "levels": [
            _lvl("lvl_rch_beg","task_isolated_phoneme_r_child","beginner",1,[
                _p("p_rch_beg_01","r","r","Hold the /r/ sound:",scope="phoneme",phonemes=["/r/"],position="isolation"),
                _p("p_rch_beg_02","ra  ra  ra","ra  ra  ra","Repeat the syllable:",scope="phoneme",phonemes=["/r/"],position="cv_syllable"),
                _p("p_rch_beg_03","ri  ri  ri","ri  ri  ri","Repeat the syllable:",scope="phoneme",phonemes=["/r/"],position="cv_syllable"),
            ]),
            _lvl("lvl_rch_int","task_isolated_phoneme_r_child","intermediate",2,[
                _p("p_rch_int_01","re  ro  ru","re  ro  ru","Say each syllable:",scope="phoneme",phonemes=["/r/"],position="cv_syllable"),
                _p("p_rch_int_02","ar  or  ur","ar  or  ur","Focus on /r/ in the final position:",scope="phoneme",phonemes=["/r/"],position="vc_syllable"),
                _p("p_rch_int_03","run  red  rope","run  red  rope","Say each word — /r/ at the start:",scope="word",phonemes=["/r/"],position="word_initial"),
            ]),
            _lvl("lvl_rch_adv","task_isolated_phoneme_r_child","advanced",3,[
                _p("p_rch_adv_01","rabbit  river  rabbit","rabbit  river  rabbit","Say these words clearly:",scope="word",phonemes=["/r/"],position="word_initial"),
                _p("p_rch_adv_02","car  star  door","car  star  door","Focus on /r/ in final position:",scope="word",phonemes=["/r/"],position="word_final"),
                _p("p_rch_adv_03","The red rabbit ran rapidly.","The red rabbit ran rapidly.","Read the sentence:",scope="sentence",phonemes=["/r/"],position="sentence_mixed"),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_kg_child",
        "name": "Isolated phoneme — /k/ and /g/ (fronting)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Isolation and syllable/word production targeting velar /k/ and /g/ for fronting.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on /k/ and /g/ primary; back-of-tongue contact is therapeutic focus",
        "defect_mappings": _dm("task_isolated_phoneme_kg_child","defect_front_child"),
        "levels": [
            _lvl("lvl_kgc_beg","task_isolated_phoneme_kg_child","beginner",1,[
                _p("p_kgc_beg_01","k","k","Say /k/ — back of tongue touches roof of mouth:",scope="phoneme",phonemes=["/k/"],position="isolation"),
                _p("p_kgc_beg_02","g","g","Say /g/ — back of tongue touches roof of mouth:",scope="phoneme",phonemes=["/g/"],position="isolation"),
                _p("p_kgc_beg_03","ka  ka  ka","ka  ka  ka","Repeat the syllable:",scope="phoneme",phonemes=["/k/"],position="cv_syllable"),
            ]),
            _lvl("lvl_kgc_int","task_isolated_phoneme_kg_child","intermediate",2,[
                _p("p_kgc_int_01","ki  ku  ko","ki  ku  ko","Say each syllable:",scope="phoneme",phonemes=["/k/"],position="cv_syllable"),
                _p("p_kgc_int_02","ga  gi  go","ga  gi  go","Say each syllable:",scope="phoneme",phonemes=["/g/"],position="cv_syllable"),
                _p("p_kgc_int_03","key  can  cup","key  can  cup","Say these words — /k/ first:",scope="word",phonemes=["/k/"],position="word_initial"),
            ]),
            _lvl("lvl_kgc_adv","task_isolated_phoneme_kg_child","advanced",3,[
                _p("p_kgc_adv_01","book  back  lock","book  back  lock","Focus on final /k/:",scope="word",phonemes=["/k/"],position="word_final"),
                _p("p_kgc_adv_02","gold  big  bag","gold  big  bag","Say each word — focus on /g/:",scope="word",phonemes=["/g/"],position="mixed_positions"),
                _p("p_kgc_adv_03","The king can kick the ball.","The king can kick the ball.","Read the sentence:",scope="sentence",phonemes=["/k/","/g/"],position="sentence_mixed"),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_cluster",
        "name": "Consonant cluster isolation drill",
        "type": "articulation", "task_mode": "repeat",
        "description": "Element-by-element and blended production of consonant clusters.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on both cluster elements; gradual blending approach",
        "defect_mappings": _dm("task_isolated_phoneme_cluster","defect_clust_child"),
        "levels": [
            _lvl("lvl_clc_beg","task_isolated_phoneme_cluster","beginner",1,[
                _p("p_clc_beg_01","s … p  →  sp","sp","Say /s/ then /p/ then blend to 'sp':",scope="phoneme"),
                _p("p_clc_beg_02","s … t  →  st","st","Say /s/ then /t/ then blend:",scope="phoneme"),
                _p("p_clc_beg_03","s … k  →  sk","sk","Say /s/ then /k/ then blend:",scope="phoneme"),
            ]),
            _lvl("lvl_clc_int","task_isolated_phoneme_cluster","intermediate",2,[
                _p("p_clc_int_01","spy  stay  sky","spy  stay  sky","Say each word — focus on the cluster:",scope="word"),
                _p("p_clc_int_02","stop  spin  skip","stop  spin  skip","Say each word:",scope="word"),
                _p("p_clc_int_03","blue  black  brown","blue  black  brown","Say each word — /bl/ cluster:",scope="word"),
            ]),
            _lvl("lvl_clc_adv","task_isolated_phoneme_cluster","advanced",3,[
                _p("p_clc_adv_01","spider  station  school","spider  station  school","Say each word clearly:",scope="word"),
                _p("p_clc_adv_02","spring  strong  splash","spring  strong  splash","Three-consonant clusters:",scope="word"),
                _p("p_clc_adv_03","The strong spider spun a sticky web.","The strong spider spun a sticky web.","Read the sentence:",scope="sentence"),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_oral_pres",
        "name": "Oral pressure consonant production (resonance)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Production of oral pressure consonants /p/ /b/ /t/ /d/ /k/ to assess and train velopharyngeal closure.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on oral pressure consonants; nasal emission is key error",
        "defect_mappings": _dm("task_isolated_phoneme_oral_pres","defect_reson_child"),
        "levels": [
            _lvl("lvl_opc_beg","task_isolated_phoneme_oral_pres","beginner",1,[
                _p("p_opc_beg_01","p  p  p","p  p  p","Puff of air — feel pressure on your lips:",scope="phoneme",phonemes=["/p/"]),
                _p("p_opc_beg_02","b  b  b","b  b  b","Feel the vibration:",scope="phoneme",phonemes=["/b/"]),
                _p("p_opc_beg_03","t  t  t","t  t  t","Tongue tip — strong burst:",scope="phoneme",phonemes=["/t/"]),
            ]),
            _lvl("lvl_opc_int","task_isolated_phoneme_oral_pres","intermediate",2,[
                _p("p_opc_int_01","pa  ba  pa  ba","pa  ba  pa  ba","Alternate oral consonants:",scope="phoneme",phonemes=["/p/","/b/"]),
                _p("p_opc_int_02","ta  da  ta  da","ta  da  ta  da","Alternate with pressure:",scope="phoneme",phonemes=["/t/","/d/"]),
                _p("p_opc_int_03","pop  bob  top","pop  bob  top","Say each word — feel the pressure:",scope="word",phonemes=["/p/","/b/","/t/"]),
            ]),
            _lvl("lvl_opc_adv","task_isolated_phoneme_oral_pres","advanced",3,[
                _p("p_opc_adv_01","Peter picked a peck of pickled peppers.","Peter picked a peck of pickled peppers.","Read — focus on /p/ pressure:",scope="sentence",phonemes=["/p/"]),
                _p("p_opc_adv_02","Betty Botter bought some butter.","Betty Botter bought some butter.","Read aloud — focus on /b/:",scope="sentence",phonemes=["/b/"]),
                _p("p_opc_adv_03","Two tiny turtles tiptoed together.","Two tiny turtles tiptoed together.","Read aloud:",scope="sentence",phonemes=["/t/"]),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_sz_adult",
        "name": "Isolated phoneme — /s/ motor re-establishment (adult)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Adult /s/ motor plan re-establishment through systematic placement cues and syllable-to-word progression.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on /s/ primary; established incorrect motor plan must be overridden",
        "defect_mappings": _dm("task_isolated_phoneme_sz_adult","defect_lisp_adult"),
        "levels": [
            _lvl("lvl_sza_beg","task_isolated_phoneme_sz_adult","beginner",1,[
                _p("p_sza_beg_01","s  s  s","s  s  s","Teeth together — tongue tip behind top teeth — hold /s/:",scope="phoneme",phonemes=["/s/"],position="isolation"),
                _p("p_sza_beg_02","ssss — zzzz","ssss — zzzz","Hold each sound 3 seconds:",scope="phoneme",phonemes=["/s/","/z/"],position="isolation"),
                _p("p_sza_beg_03","sa  sa  sa  si  si  si","sa  sa  sa  si  si  si","Syllable practice:",scope="phoneme",phonemes=["/s/"],position="cv_syllable"),
            ]),
            _lvl("lvl_sza_int","task_isolated_phoneme_sz_adult","intermediate",2,[
                _p("p_sza_int_01","see  sew  so","see  sew  so","Word-initial /s/:",scope="word",phonemes=["/s/"],position="word_initial"),
                _p("p_sza_int_02","miss  loss  pass","miss  loss  pass","Word-final /s/:",scope="word",phonemes=["/s/"],position="word_final"),
                _p("p_sza_int_03","sister  essen  lesson","sister  essen  lesson","Medial /s/:",scope="word",phonemes=["/s/"],position="word_medial"),
            ]),
            _lvl("lvl_sza_adv","task_isolated_phoneme_sz_adult","advanced",3,[
                _p("p_sza_adv_01","Susan sees seven seals.","Susan sees seven seals.","Read the sentence clearly:",scope="sentence",phonemes=["/s/"],position="sentence_mixed"),
                _p("p_sza_adv_02","The business is a success.","The business is a success.","Read aloud:",scope="sentence",phonemes=["/s/","/z/"],position="sentence_mixed"),
                _p("p_sza_adv_03","She is busy sorting scissors and glasses.","She is busy sorting scissors and glasses.","Read aloud naturally:",scope="sentence",phonemes=["/s/","/z/"],position="sentence_mixed"),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_r_adult",
        "name": "Isolated phoneme — /r/ motor re-establishment (adult)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Post-neurological /r/ re-establishment through systematic cues and graded syllable/word practice.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "PA on /r/ is primary; effortful production is expected initially",
        "defect_mappings": _dm("task_isolated_phoneme_r_adult","defect_rhot_adult"),
        "levels": [
            _lvl("lvl_rad_beg","task_isolated_phoneme_r_adult","beginner",1,[
                _p("p_rad_beg_01","r  r  r","r  r  r","Curl tongue tip — produce /r/:",scope="phoneme",phonemes=["/r/"],position="isolation"),
                _p("p_rad_beg_02","ra  ra  ra","ra  ra  ra","Repeat the syllable:",scope="phoneme",phonemes=["/r/"],position="cv_syllable"),
                _p("p_rad_beg_03","rrr — ra — rrr — ra","rrr — ra — rrr — ra","Alternate held /r/ and syllable:",scope="phoneme",phonemes=["/r/"],position="mixed_sequence"),
            ]),
            _lvl("lvl_rad_int","task_isolated_phoneme_r_adult","intermediate",2,[
                _p("p_rad_int_01","red  run  rain","red  run  rain","Word-initial /r/:",scope="word",phonemes=["/r/"],position="word_initial"),
                _p("p_rad_int_02","car  far  more","car  far  more","Word-final /r/:",scope="word",phonemes=["/r/"],position="word_final"),
                _p("p_rad_int_03","very  carry  erry","very  carry  erry","Medial /r/:",scope="word",phonemes=["/r/"],position="word_medial"),
            ]),
            _lvl("lvl_rad_adv","task_isolated_phoneme_r_adult","advanced",3,[
                _p("p_rad_adv_01","The red car ran far.","The red car ran far.","Read the sentence:",scope="sentence",phonemes=["/r/"],position="sentence_mixed"),
                _p("p_rad_adv_02","River rafting requires real courage.","River rafting requires real courage.","Read aloud:",scope="sentence",phonemes=["/r/"],position="sentence_mixed"),
                _p("p_rad_adv_03","The report arrived very rapidly.","The report arrived very rapidly.","Read naturally:",scope="sentence",phonemes=["/r/"],position="sentence_mixed"),
            ]),
        ],
    },

    {
        "task_id": "task_isolated_phoneme_cas",
        "name": "Consistent motor plan production (CAS)",
        "type": "articulation", "task_mode": "repeat",
        "description": "Repeated productions of the same target to establish consistent motor plans for CAS.",
        "wpm_category": "phoneme", "weight_category": "articulation_phoneme",
        "scoring_notes": "Consistency across trials is the key CAS metric, not single-trial PA",
        "defect_mappings": _dm("task_isolated_phoneme_cas","defect_cas_child"),
        "levels": [
            _lvl("lvl_cas_beg","task_isolated_phoneme_cas","beginner",1,[
                _p("p_cas_beg_01","ma  ma  ma  ma","ma  ma  ma  ma","Repeat exactly the same way each time:",scope="phoneme"),
                _p("p_cas_beg_02","ba  ba  ba  ba","ba  ba  ba  ba","Repeat consistently:",scope="phoneme"),
                _p("p_cas_beg_03","da  da  da  da","da  da  da  da","Same each time:",scope="phoneme"),
            ]),
            _lvl("lvl_cas_int","task_isolated_phoneme_cas","intermediate",2,[
                _p("p_cas_int_01","mummy  mummy  mummy","mummy  mummy  mummy","Say consistently three times:",scope="word"),
                _p("p_cas_int_02","baby  baby  baby","baby  baby  baby","Repeat consistently:",scope="word"),
                _p("p_cas_int_03","daddy  daddy  daddy","daddy  daddy  daddy","Same each time:",scope="word"),
            ]),
            _lvl("lvl_cas_adv","task_isolated_phoneme_cas","advanced",3,[
                _p("p_cas_adv_01","I want a banana.","I want a banana.","Say clearly three times in a row:",scope="sentence"),
                _p("p_cas_adv_02","My name is ___. (say your name)","(say your name phrase)","Practise your name phrase:",scope="sentence"),
                _p("p_cas_adv_03","Hello my name is ___","Hello my name is ___","Practise this greeting consistently:",scope="sentence"),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # FLUENCY TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_slow_prolonged_speech",
        "name": "Slow and prolonged speech",
        "type": "fluency", "task_mode": "read_aloud",
        "description": "Stretch vowels and slow overall rate to reduce disfluency and increase fluency confidence.",
        "wpm_category": "fluency", "weight_category": "fluency",
        "scoring_notes": "FS is primary; SRS monitors that rate is slowed sufficiently",
        "defect_mappings": _dm("task_slow_prolonged_speech",
            "defect_devstut_child","defect_neurstut_adult","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_sps_beg","task_slow_prolonged_speech","beginner",1,[
                _p("p_sps_beg_01","Hellooo. My naame is ___.",None,
                   "Stretch every vowel. Go very slowly:",scope="sentence",task_type="fluency",
                   pass_msg="Great control of rate!"),
                _p("p_sps_beg_02","I liike to eeat.",None,
                   "Read slowly, stretching vowels:",scope="sentence",task_type="fluency"),
                _p("p_sps_beg_03","The suun is waarm todaay.",None,
                   "Read aloud very slowly:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_sps_int","task_slow_prolonged_speech","intermediate",2,[
                _p("p_sps_int_01","I am going to the shop today.",None,
                   "Use slow prolonged speech — stretch vowels:",scope="sentence",task_type="fluency"),
                _p("p_sps_int_02","The weather is nice and sunny.",None,
                   "Read slowly and smoothly:",scope="sentence",task_type="fluency"),
                _p("p_sps_int_03","My family likes to go for walks.",None,
                   "Read with elongated vowels and slow pace:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_sps_adv","task_slow_prolonged_speech","advanced",3,[
                _p("p_sps_adv_01","I enjoy spending time at the park on weekends.",None,
                   "Speak slowly and fluently:",scope="sentence",task_type="fluency"),
                _p("p_sps_adv_02","Yesterday I went shopping and bought some food.",None,
                   "Use prolonged speech throughout:",scope="sentence",task_type="fluency"),
                _p("p_sps_adv_03","Tell me about your plans for tomorrow.",None,
                   "Answer using slow prolonged speech:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=20,min_words=15),
            ]),
        ],
    },

    {
        "task_id": "task_easy_onset",
        "name": "Easy onset — light articulatory contact",
        "type": "fluency", "task_mode": "repeat",
        "description": "Initiate voice gently with soft articulatory contacts to reduce blocking and struggle.",
        "wpm_category": "fluency", "weight_category": "fluency",
        "scoring_notes": "FS primary; CS captures voice onset quality",
        "defect_mappings": _dm("task_easy_onset",
            "defect_devstut_child","defect_neurstut_adult","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_eon_beg","task_easy_onset","beginner",1,[
                _p("p_eon_beg_01","apple","apple","Begin very gently — soft voice start:",scope="word",task_type="fluency"),
                _p("p_eon_beg_02","open","open","Easy gentle onset:",scope="word",task_type="fluency"),
                _p("p_eon_beg_03","only","only","Start your voice softly:",scope="word",task_type="fluency"),
            ]),
            _lvl("lvl_eon_int","task_easy_onset","intermediate",2,[
                _p("p_eon_int_01","I am ready.","I am ready.","Use easy onset on 'I' — gentle start:",scope="sentence",task_type="fluency"),
                _p("p_eon_int_02","All of us are here.","All of us are here.","Easy onset throughout:",scope="sentence",task_type="fluency"),
                _p("p_eon_int_03","Every morning I wake up early.","Every morning I wake up early.","Gentle voice starts:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_eon_adv","task_easy_onset","advanced",3,[
                _p("p_eon_adv_01","In our office we always aim for accuracy.",None,
                   "Apply easy onset to all words — especially vowel-initial:",scope="sentence",task_type="fluency"),
                _p("p_eon_adv_02","I ordered eggs and orange juice at eight.",None,"Read with easy onset:",scope="sentence",task_type="fluency"),
                _p("p_eon_adv_03","Introduce yourself using easy onset on every word.",None,
                   "Speak naturally with easy onset technique:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=20,min_words=15),
            ]),
        ],
    },

    {
        "task_id": "task_diaphragmatic_breathing",
        "name": "Diaphragmatic breathing for speech",
        "type": "fluency", "task_mode": "spontaneous",
        "description": "Coordinate diaphragmatic breathing with speech to support fluency and reduce anxiety.",
        "wpm_category": "fluency", "weight_category": "fluency",
        "scoring_notes": "FS and CS are primary; engagement score reflects relaxation",
        "defect_mappings": _dm("task_diaphragmatic_breathing",
            "defect_devstut_child","defect_mute_child","defect_neurstut_adult","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_dbr_beg","task_diaphragmatic_breathing","beginner",1,[
                _p("p_dbr_beg_01","one","one","Breathe in, then say the word on the out-breath:",scope="word",task_type="fluency"),
                _p("p_dbr_beg_02","hello","hello","Deep breath in — say 'hello' gently:",scope="word",task_type="fluency"),
                _p("p_dbr_beg_03","yes","yes","Breathe in deeply — say 'yes' on your exhale:",scope="word",task_type="fluency"),
            ]),
            _lvl("lvl_dbr_int","task_diaphragmatic_breathing","intermediate",2,[
                _p("p_dbr_int_01","I am calm and ready.","I am calm and ready.",
                   "Breathe in — say the phrase on one breath:",scope="sentence",task_type="fluency"),
                _p("p_dbr_int_02","Today is a good day.","Today is a good day.",
                   "Breathe before speaking:",scope="sentence",task_type="fluency"),
                _p("p_dbr_int_03","I can speak clearly and calmly.","I can speak clearly and calmly.",
                   "Breath support for the full phrase:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_dbr_adv","task_diaphragmatic_breathing","advanced",3,[
                _p("p_dbr_adv_01","Tell me one thing you enjoy doing.",None,
                   "Take a breath, then answer calmly:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=20,min_words=10),
                _p("p_dbr_adv_02","Describe your home in a few sentences.",None,
                   "Breathe before each sentence:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=30,min_words=15),
                _p("p_dbr_adv_03","Say your name and address slowly.",None,
                   "Breathe and speak with full support:",scope="sentence",task_type="fluency"),
            ]),
        ],
    },

    {
        "task_id": "task_stutter_cancellation",
        "name": "Stutter cancellation technique",
        "type": "fluency", "task_mode": "spontaneous",
        "description": "Practise voluntary stuttering followed by cancellation — stop, pause, then re-say with easy onset.",
        "wpm_category": "spontaneous", "weight_category": "fluency",
        "scoring_notes": "FS primary — cancellation reduces secondary struggle behaviours",
        "defect_mappings": _dm("task_stutter_cancellation",
            "defect_devstut_child","defect_neurstut_adult","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_stc_beg","task_stutter_cancellation","beginner",1,[
                _p("p_stc_beg_01","big","big","Voluntary stutter on /b/ — then pause — then say it smoothly:",scope="word",task_type="fluency"),
                _p("p_stc_beg_02","table","table","Repeat with cancellation technique:",scope="word",task_type="fluency"),
                _p("p_stc_beg_03","morning","morning","Stutter — pause — cancel — re-say:",scope="word",task_type="fluency"),
            ]),
            _lvl("lvl_stc_int","task_stutter_cancellation","intermediate",2,[
                _p("p_stc_int_01","I want some water.","I want some water.",
                   "Introduce a stutter on a word — then cancel it:",scope="sentence",task_type="fluency"),
                _p("p_stc_int_02","My name is ___.",None,
                   "Say your name — if you stutter, cancel and re-say:",scope="sentence",task_type="fluency"),
                _p("p_stc_int_03","Can I have the menu please?","Can I have the menu please?",
                   "Apply cancellation if you stutter:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_stc_adv","task_stutter_cancellation","advanced",3,[
                _p("p_stc_adv_01","Tell me about your favourite film.",None,
                   "Speak freely — cancel any stutters:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=30,min_words=20),
                _p("p_stc_adv_02","Order a coffee at a café.",None,
                   "Role-play the situation — use cancellation:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=20,min_words=10),
                _p("p_stc_adv_03","Introduce yourself in a meeting.",None,
                   "Speak fluently using cancellation as needed:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=25,min_words=15),
            ]),
        ],
    },

    {
        "task_id": "task_rate_control_pause",
        "name": "Rate control and phrasing pauses",
        "type": "fluency", "task_mode": "read_aloud",
        "description": "Read with deliberate phrasing pauses and controlled rate to improve naturalness and reduce disfluency.",
        "wpm_category": "fluency", "weight_category": "fluency",
        "scoring_notes": "SRS measures rate; FS measures smoothness of phrasing",
        "defect_mappings": _dm("task_rate_control_pause",
            "defect_devstut_child","defect_clutter_child","defect_clutter_adult"),
        "levels": [
            _lvl("lvl_rcp_beg","task_rate_control_pause","beginner",1,[
                _p("p_rcp_beg_01","I like cats. | They are soft. | They purr.",None,
                   "Read — pause at each | mark:",scope="sentence",task_type="fluency"),
                _p("p_rcp_beg_02","She went home. | She had dinner. | She slept.",None,
                   "Pause at each | mark — do not rush:",scope="sentence",task_type="fluency"),
                _p("p_rcp_beg_03","The dog ran fast. | It caught the ball. | Good dog.",None,
                   "Read with clear pauses:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_rcp_int","task_rate_control_pause","intermediate",2,[
                _p("p_rcp_int_01","I went to the market | and bought some vegetables | and some fruit.",None,
                   "Read — pause at | marks — steady rate:",scope="sentence",task_type="fluency"),
                _p("p_rcp_int_02","The children played outside | until the sun went down | and it got cold.",None,
                   "Read with phrasing pauses:",scope="sentence",task_type="fluency"),
                _p("p_rcp_int_03","She opened the door | stepped inside | and turned on the light.",None,
                   "Pause at | marks:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_rcp_adv","task_rate_control_pause","advanced",3,[
                _p("p_rcp_adv_01","Yesterday I went to the park with my family and we had a picnic near the lake.",None,
                   "Read at a steady controlled pace — insert pauses where natural:",scope="sentence",task_type="fluency"),
                _p("p_rcp_adv_02","Tell me what you did this morning — speak at a slow, steady rate.",None,
                   "Answer with controlled rate and clear pauses:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=25,min_words=15),
                _p("p_rcp_adv_03","The annual report showed that sales had increased significantly over the previous quarter.",None,
                   "Read this long sentence at a measured pace:",scope="sentence",task_type="fluency"),
            ]),
        ],
    },

    {
        "task_id": "task_prosody_rhythm",
        "name": "Prosody and speech rhythm",
        "type": "fluency", "task_mode": "read_aloud",
        "description": "Read with appropriate stress, intonation, and rhythm patterns to improve naturalness.",
        "wpm_category": "sentence", "weight_category": "fluency",
        "scoring_notes": "FS captures prosodic smoothness; WA monitors articulatory accuracy during rhythm tasks",
        "defect_mappings": _dm("task_prosody_rhythm",
            "defect_devstut_child","defect_clutter_child","defect_clutter_adult","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_pry_beg","task_prosody_rhythm","beginner",1,[
                _p("p_pry_beg_01","RED car. BLUE sky. BIG dog.","RED car. BLUE sky. BIG dog.",
                   "Emphasise the CAPITAL word in each phrase:",scope="sentence",task_type="fluency"),
                _p("p_pry_beg_02","I LIKE it. She RUNS fast. He WENT home.","I LIKE it. She RUNS fast. He WENT home.",
                   "Stress the bold word:",scope="sentence",task_type="fluency"),
                _p("p_pry_beg_03","The BIG brown bear.","The BIG brown bear.",
                   "Say with natural stress:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_pry_int","task_prosody_rhythm","intermediate",2,[
                _p("p_pry_int_01","Is it COLD today? Yes, it IS cold.","Is it COLD today? Yes, it IS cold.",
                   "Read with natural question and answer intonation:",scope="sentence",task_type="fluency"),
                _p("p_pry_int_02","She went to the MARKET, not the SCHOOL.",None,
                   "Stress the contrasted words:",scope="sentence",task_type="fluency"),
                _p("p_pry_int_03","I did NOT say that. I said THIS.",None,
                   "Read with contrastive stress:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_pry_adv","task_prosody_rhythm","advanced",3,[
                _p("p_pry_adv_01","The weather today is surprisingly warm for this time of year.",None,
                   "Read with natural prosody and appropriate stress:",scope="sentence",task_type="fluency"),
                _p("p_pry_adv_02","Good morning, everyone. I am delighted to speak with you today.",None,
                   "Read as if addressing an audience:",scope="sentence",task_type="fluency"),
                _p("p_pry_adv_03","Tell me a short story — focus on using natural rhythm and intonation.",None,
                   "Speak with natural prosody:",scope="discourse",task_type="fluency",
                   tc_mode="duration",target_dur=30,min_words=20),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # LANGUAGE TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_convo_turntaking",
        "name": "Conversational turn-taking",
        "type": "language", "task_mode": "answer",
        "description": "Practise initiating, maintaining, and yielding conversational turns appropriately.",
        "wpm_category": "conversation", "weight_category": "language",
        "scoring_notes": "WA primary; FS captures naturalness of turn transitions",
        "defect_mappings": _dm("task_convo_turntaking",
            "defect_exprlang_child","defect_reclang_child","defect_latelang_child",
            "defect_asd_child","defect_anomia_adult","defect_aphrec_adult","defect_aphexpr_adult"),
        "levels": [
            _lvl("lvl_ctt_beg","task_convo_turntaking","beginner",1,[
                _p("p_ctt_beg_01","What is your name?",None,"Answer the question:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=5,min_words=2),
                _p("p_ctt_beg_02","How old are you?",None,"Answer the question:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=5,min_words=2),
                _p("p_ctt_beg_03","Do you have a pet?",None,"Answer yes or no and say one more thing:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=8,min_words=3),
            ]),
            _lvl("lvl_ctt_int","task_convo_turntaking","intermediate",2,[
                _p("p_ctt_int_01","What did you do yesterday?",None,"Answer in 2-3 sentences:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=10),
                _p("p_ctt_int_02","Tell me about your family.",None,"Describe your family briefly:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=25,min_words=12),
                _p("p_ctt_int_03","What is your favourite food and why?",None,"Answer fully:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=25,min_words=12),
            ]),
            _lvl("lvl_ctt_adv","task_convo_turntaking","advanced",3,[
                _p("p_ctt_adv_01","Tell me about a problem you solved recently.",None,
                   "Answer in full sentences with detail:",scope="discourse",task_type="language",tc_mode="duration",target_dur=30,min_words=25),
                _p("p_ctt_adv_02","What would you do if you won the lottery?",None,
                   "Elaborate your answer:",scope="discourse",task_type="language",tc_mode="duration",target_dur=30,min_words=25),
                _p("p_ctt_adv_03","Describe a film or book you enjoyed recently.",None,
                   "Give a detailed response:",scope="discourse",task_type="language",tc_mode="duration",target_dur=40,min_words=30),
            ]),
        ],
    },

    {
        "task_id": "task_wh_question",
        "name": "WH-question comprehension and production",
        "type": "language", "task_mode": "answer",
        "description": "Answer and produce WH-questions (who, what, where, when, why) to build language structure.",
        "wpm_category": "spontaneous", "weight_category": "language",
        "scoring_notes": "WA primary — keyword accuracy in answer is key measure",
        "defect_mappings": _dm("task_wh_question",
            "defect_exprlang_child","defect_reclang_child","defect_asd_child",
            "defect_aphexpr_adult","defect_anomia_adult"),
        "levels": [
            _lvl("lvl_whq_beg","task_wh_question","beginner",1,[
                _p("p_whq_beg_01","Who is in your family?",None,"Answer with names or roles:",scope="word",task_type="language",tc_mode="word_count",target_wc=8,min_words=2),
                _p("p_whq_beg_02","What colour is the sky?",None,"Answer the question:",scope="word",task_type="language",tc_mode="word_count",target_wc=5,min_words=1),
                _p("p_whq_beg_03","Where do you live?",None,"Say your city or neighbourhood:",scope="word",task_type="language",tc_mode="word_count",target_wc=5,min_words=2),
            ]),
            _lvl("lvl_whq_int","task_wh_question","intermediate",2,[
                _p("p_whq_int_01","What do you do when you feel sad?",None,"Answer in a full sentence:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=8),
                _p("p_whq_int_02","Where would you go for a holiday?",None,"Answer with detail:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=8),
                _p("p_whq_int_03","Why do you like your favourite food?",None,"Explain your reason:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=10),
            ]),
            _lvl("lvl_whq_adv","task_wh_question","advanced",3,[
                _p("p_whq_adv_01","Why is it important to exercise regularly?",None,"Give 2-3 reasons:",scope="discourse",task_type="language",tc_mode="duration",target_dur=25,min_words=20),
                _p("p_whq_adv_02","When did you last feel proud of yourself, and why?",None,"Answer fully:",scope="discourse",task_type="language",tc_mode="duration",target_dur=30,min_words=20),
                _p("p_whq_adv_03","How would you explain the internet to someone who has never used it?",None,"Explain clearly:",scope="discourse",task_type="language",tc_mode="duration",target_dur=35,min_words=25),
            ]),
        ],
    },

    {
        "task_id": "task_following_instructions",
        "name": "Following multi-step instructions",
        "type": "language", "task_mode": "answer",
        "description": "Listen and follow increasingly complex instructions to build auditory processing and comprehension.",
        "wpm_category": "spontaneous", "weight_category": "language",
        "scoring_notes": "WA primary — confirms the patient heard and understood each step",
        "defect_mappings": _dm("task_following_instructions",
            "defect_exprlang_child","defect_reclang_child","defect_latelang_child","defect_aphrec_adult"),
        "levels": [
            _lvl("lvl_fis_beg","task_following_instructions","beginner",1,[
                _p("p_fis_beg_01","Touch your nose.",None,"Do the action and say what you did:",scope="word",task_type="language",tc_mode="word_count",target_wc=5,min_words=2),
                _p("p_fis_beg_02","Clap two times.",None,"Do it and say: 'I clapped two times.'",scope="word",task_type="language",tc_mode="word_count",target_wc=5,min_words=3),
                _p("p_fis_beg_03","Stand up.",None,"Do it and say the action:",scope="word",task_type="language",tc_mode="word_count",target_wc=3,min_words=1),
            ]),
            _lvl("lvl_fis_int","task_following_instructions","intermediate",2,[
                _p("p_fis_int_01","Touch your head, then your shoulder, then your knee.",None,
                   "Follow the instructions in order and describe what you did:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=8),
                _p("p_fis_int_02","Pick up something red, put it on the table, then sit down.",None,
                   "Carry out the steps and describe them:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=8),
                _p("p_fis_int_03","Say your name, spell it, and give your age.",None,
                   "Complete all three steps:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=8),
            ]),
            _lvl("lvl_fis_adv","task_following_instructions","advanced",3,[
                _p("p_fis_adv_01","Count from 10 to 1, clap on every even number.",None,
                   "Follow the instruction carefully:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=10),
                _p("p_fis_adv_02","Say the days of the week backwards, skipping Wednesday.",None,
                   "Complete the task:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=6),
                _p("p_fis_adv_03","Name three animals, then use one in a sentence.",None,
                   "Complete all steps:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=10),
            ]),
        ],
    },

    {
        "task_id": "task_picture_naming",
        "name": "Picture naming / word retrieval",
        "type": "language", "task_mode": "describe",
        "description": "Name pictures or describe objects to practise word retrieval and lexical access.",
        "wpm_category": "word", "weight_category": "language",
        "scoring_notes": "WA primary — target word must be produced accurately",
        "defect_mappings": _dm("task_picture_naming",
            "defect_exprlang_child","defect_reclang_child","defect_latelang_child",
            "defect_aphexpr_adult","defect_anomia_adult"),
        "levels": [
            _lvl("lvl_pna_beg","task_picture_naming","beginner",1,[
                _p("p_pna_beg_01","cat","cat","Name the picture:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_pna_beg_02","cup","cup","Name the picture:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_pna_beg_03","sun","sun","Name the picture:",scope="word",task_type="language",tc_mode="completion"),
            ]),
            _lvl("lvl_pna_int","task_picture_naming","intermediate",2,[
                _p("p_pna_int_01","elephant","elephant","Name the animal:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_pna_int_02","scissors","scissors","Name the object:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_pna_int_03","umbrella","umbrella","Name the object:",scope="word",task_type="language",tc_mode="completion"),
            ]),
            _lvl("lvl_pna_adv","task_picture_naming","advanced",3,[
                _p("p_pna_adv_01","stethoscope","stethoscope","Name the object:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_pna_adv_02","compass","compass","Name the item:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_pna_adv_03","microscope","microscope","Name the picture and say a sentence about it:",
                   scope="discourse",task_type="language",tc_mode="word_count",target_wc=10,min_words=5),
            ]),
        ],
    },

    {
        "task_id": "task_narrative_retelling",
        "name": "Narrative retelling",
        "type": "language", "task_mode": "describe",
        "description": "Retell a story or event with appropriate structure (beginning, middle, end).",
        "wpm_category": "spontaneous", "weight_category": "language",
        "scoring_notes": "WA and FS capture content accuracy and coherence",
        "defect_mappings": _dm("task_narrative_retelling",
            "defect_exprlang_child","defect_reclang_child","defect_latelang_child",
            "defect_aphexpr_adult","defect_aphrec_adult","defect_anomia_adult"),
        "levels": [
            _lvl("lvl_nre_beg","task_narrative_retelling","beginner",1,[
                _p("p_nre_beg_01","A dog found a ball. He played with it.",None,
                   "Listen, then tell it back in your own words:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=10,min_words=5),
                _p("p_nre_beg_02","A girl went to the shop. She bought milk.",None,"Retell the story:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=10,min_words=5),
                _p("p_nre_beg_03","A boy kicked the ball. It went over the fence.",None,"Retell in your own words:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=10,min_words=5),
            ]),
            _lvl("lvl_nre_int","task_narrative_retelling","intermediate",2,[
                _p("p_nre_int_01","Yesterday I went to the market. I bought vegetables and fruit. Then I went home and cooked.",None,
                   "Retell in your own words:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=12),
                _p("p_nre_int_02","Tell me a short story about something that happened to you.",None,
                   "Tell the story — beginning, middle, end:",scope="discourse",task_type="language",tc_mode="duration",target_dur=30,min_words=20),
                _p("p_nre_int_03","Three Billy Goats Gruff story summary.",None,
                   "Retell the story:",scope="discourse",task_type="language",tc_mode="duration",target_dur=30,min_words=20),
            ]),
            _lvl("lvl_nre_adv","task_narrative_retelling","advanced",3,[
                _p("p_nre_adv_01","Retell the last film or TV show you watched.",None,
                   "Give a full account — beginning to end:",scope="discourse",task_type="language",tc_mode="duration",target_dur=45,min_words=35),
                _p("p_nre_adv_02","Tell me about an important event in your life.",None,
                   "Give a structured narrative:",scope="discourse",task_type="language",tc_mode="duration",target_dur=45,min_words=35),
                _p("p_nre_adv_03","Retell the Goldilocks story.",None,
                   "Retell with detail:",scope="discourse",task_type="language",tc_mode="duration",target_dur=40,min_words=30),
            ]),
        ],
    },

    {
        "task_id": "task_sentence_completion",
        "name": "Sentence completion",
        "type": "language", "task_mode": "fill_blank",
        "description": "Complete sentence frames to practise word retrieval and syntax.",
        "wpm_category": "word", "weight_category": "language",
        "scoring_notes": "WA primary — completion word must be semantically and syntactically appropriate",
        "defect_mappings": _dm("task_sentence_completion",
            "defect_exprlang_child","defect_latelang_child","defect_aphexpr_adult","defect_anomia_adult"),
        "levels": [
            _lvl("lvl_scp_beg","task_sentence_completion","beginner",1,[
                _p("p_scp_beg_01","The sky is ___. (blue)","blue","Complete the sentence with the right word:",scope="word",task_type="language"),
                _p("p_scp_beg_02","Cats say ___. (meow)","meow","Complete the sentence:",scope="word",task_type="language"),
                _p("p_scp_beg_03","We sleep at ___. (night)","night","Complete the sentence:",scope="word",task_type="language"),
            ]),
            _lvl("lvl_scp_int","task_sentence_completion","intermediate",2,[
                _p("p_scp_int_01","I brush my teeth with a ___. (toothbrush)","toothbrush","Complete the sentence:",scope="word",task_type="language"),
                _p("p_scp_int_02","You use a ___ to cut paper. (scissors)","scissors","Complete:",scope="word",task_type="language"),
                _p("p_scp_int_03","When it rains you carry an ___. (umbrella)","umbrella","Complete the sentence:",scope="word",task_type="language"),
            ]),
            _lvl("lvl_scp_adv","task_sentence_completion","advanced",3,[
                _p("p_scp_adv_01","Despite the heavy rain, the match ___ (continued)","continued","Complete with a verb:",scope="word",task_type="language"),
                _p("p_scp_adv_02","She was so tired that she could barely ___. (stay awake)","stay awake","Complete the sentence:",scope="word",task_type="language"),
                _p("p_scp_adv_03","The experiment failed because the scientists ___ the wrong formula.","used","Complete:",scope="word",task_type="language"),
            ]),
        ],
    },

    {
        "task_id": "task_complex_instruction",
        "name": "Complex multi-step instruction following",
        "type": "language", "task_mode": "answer",
        "description": "Follow complex two- and three-step instructions involving conditionals and sequences.",
        "wpm_category": "spontaneous", "weight_category": "language",
        "scoring_notes": "WA measures accuracy of all steps; FS captures response organisation",
        "defect_mappings": _dm("task_complex_instruction","defect_reclang_child","defect_aphrec_adult"),
        "levels": [
            _lvl("lvl_cxi_beg","task_complex_instruction","beginner",1,[
                _p("p_cxi_beg_01","Put your hands up if you are sitting down.",None,"Listen and follow:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_cxi_beg_02","Touch your nose, then your chin.",None,"Follow both steps:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_cxi_beg_03","Say 'yes' if you like dogs, 'no' if you like cats.",None,"Listen and respond correctly:",scope="word",task_type="language",tc_mode="completion"),
            ]),
            _lvl("lvl_cxi_int","task_complex_instruction","intermediate",2,[
                _p("p_cxi_int_01","Before you say your name, clap once.",None,"Follow the instruction:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=8,min_words=3),
                _p("p_cxi_int_02","Clap twice, then say the name of a colour, then sit down.",None,"Follow all three steps:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=10,min_words=5),
                _p("p_cxi_int_03","If today is not Monday, tell me what day it is.",None,"Listen and respond:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=10,min_words=4),
            ]),
            _lvl("lvl_cxi_adv","task_complex_instruction","advanced",3,[
                _p("p_cxi_adv_01","Say three words that start with the same letter, then use one in a sentence.",None,"Follow the instruction:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=8),
                _p("p_cxi_adv_02","Tell me two things you did this morning and one thing you plan to do tonight.",None,"Answer all parts:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=12),
                _p("p_cxi_adv_03","Give me an example of a mammal, then explain in one sentence why it is a mammal.",None,"Answer fully:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=12),
            ]),
        ],
    },

    {
        "task_id": "task_word_assoc_semantic",
        "name": "Word association and semantic retrieval",
        "type": "language", "task_mode": "answer",
        "description": "Retrieve semantically related words and explain connections to strengthen lexical networks.",
        "wpm_category": "word", "weight_category": "language",
        "scoring_notes": "WA primary — semantic accuracy of retrieved words",
        "defect_mappings": _dm("task_word_assoc_semantic","defect_aphexpr_adult","defect_anomia_adult"),
        "levels": [
            _lvl("lvl_was_beg","task_word_assoc_semantic","beginner",1,[
                _p("p_was_beg_01","Say a word that goes with 'dog'.",None,"Say one related word:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_was_beg_02","Say a word that goes with 'kitchen'.",None,"Say one related word:",scope="word",task_type="language",tc_mode="completion"),
                _p("p_was_beg_03","Say a word that goes with 'rain'.",None,"Say one related word:",scope="word",task_type="language",tc_mode="completion"),
            ]),
            _lvl("lvl_was_int","task_word_assoc_semantic","intermediate",2,[
                _p("p_was_int_01","Name three things you find in a hospital.",None,"Name three items:",scope="word",task_type="language",tc_mode="word_count",target_wc=6,min_words=3),
                _p("p_was_int_02","Name three things you use when cooking.",None,"Name three items:",scope="word",task_type="language",tc_mode="word_count",target_wc=6,min_words=3),
                _p("p_was_int_03","Name three animals that live in water.",None,"Name three animals:",scope="word",task_type="language",tc_mode="word_count",target_wc=6,min_words=3),
            ]),
            _lvl("lvl_was_adv","task_word_assoc_semantic","advanced",3,[
                _p("p_was_adv_01","Name five things in a bedroom and say what each is used for.",None,
                   "Name each item and give its purpose:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=25,min_words=15),
                _p("p_was_adv_02","Describe the word 'freedom' without using the word itself.",None,
                   "Describe it in your own words:",scope="discourse",task_type="language",tc_mode="duration",target_dur=20,min_words=12),
                _p("p_was_adv_03","What is the difference between a lawyer and a judge?",None,
                   "Explain the difference:",scope="discourse",task_type="language",tc_mode="duration",target_dur=25,min_words=15),
            ]),
        ],
    },

    {
        "task_id": "task_sentence_reading_paced",
        "name": "Paced sentence reading",
        "type": "articulation", "task_mode": "read_aloud",
        "description": "Read sentences at a controlled pace with clear articulation, targeting motor speech disorders and cluttering.",
        "wpm_category": "sentence", "weight_category": "articulation_sentence",
        "scoring_notes": "WA and PA both measured; SRS confirms controlled rate",
        "defect_mappings": _dm("task_sentence_reading_paced",
            "defect_clutter_child","defect_dysart_adult","defect_aos_adult",
            "defect_hypodys_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_srp_beg","task_sentence_reading_paced","beginner",1,[
                _p("p_srp_beg_01","The cat sat on the mat.","The cat sat on the mat.","Read clearly at a slow pace:",scope="sentence"),
                _p("p_srp_beg_02","I like to eat fruit.","I like to eat fruit.","Read clearly:",scope="sentence"),
                _p("p_srp_beg_03","The dog ran to the park.","The dog ran to the park.","Read at a steady rate:",scope="sentence"),
            ]),
            _lvl("lvl_srp_int","task_sentence_reading_paced","intermediate",2,[
                _p("p_srp_int_01","She walked slowly down the quiet street.","She walked slowly down the quiet street.","Read at a comfortable pace:",scope="sentence"),
                _p("p_srp_int_02","The children played outside until dinner time.","The children played outside until dinner time.","Read clearly and steadily:",scope="sentence"),
                _p("p_srp_int_03","He carefully opened the letter and began to read.","He carefully opened the letter and began to read.","Read with clear articulation:",scope="sentence"),
            ]),
            _lvl("lvl_srp_adv","task_sentence_reading_paced","advanced",3,[
                _p("p_srp_adv_01","The organisation announced new environmental policies at the annual conference.",
                   "The organisation announced new environmental policies at the annual conference.",
                   "Read at a measured, clear pace:",scope="sentence"),
                _p("p_srp_adv_02","Despite the challenging conditions, the rescue team located all three survivors.",
                   "Despite the challenging conditions, the rescue team located all three survivors.",
                   "Read with precise articulation:",scope="sentence"),
                _p("p_srp_adv_03","The scientists published their findings in a peer-reviewed journal last month.",
                   "The scientists published their findings in a peer-reviewed journal last month.",
                   "Read clearly at a steady pace:",scope="sentence"),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # VOICE TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_vocal_warmup",
        "name": "Vocal warmup sequence",
        "type": "voice", "task_mode": "imitate",
        "description": "Systematic vocal warmup — humming, lip trills, and sirens to prepare the voice for extended use.",
        "wpm_category": "phoneme", "weight_category": "voice",
        "scoring_notes": "CS and FS capture vocal quality and ease; PA less relevant for warmup",
        "defect_mappings": _dm("task_vocal_warmup",
            "defect_clutter_child","defect_vocnod_child","defect_reson_child",
            "defect_vocnod_adult","defect_vcpar_adult","defect_spasdys_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_vwu_beg","task_vocal_warmup","beginner",1,[
                _p("p_vwu_beg_01","mmm  (hum for 5 seconds)","mmm","Hum gently for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
                _p("p_vwu_beg_02","brrrrr  (lip trill)",None,"Lip trill — blow air through relaxed lips for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
                _p("p_vwu_beg_03","ahhh  (easy onset)","ahh","Open your mouth — say 'ah' gently:",scope="phoneme",task_type="voice"),
            ]),
            _lvl("lvl_vwu_int","task_vocal_warmup","intermediate",2,[
                _p("p_vwu_int_01","mmmm — moving up in pitch","mmm up scale","Hum and slide pitch upward:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=8),
                _p("p_vwu_int_02","wooooo  (siren — up and down)","wooo siren","Siren up and down on 'woo':",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=8),
                _p("p_vwu_int_03","v-v-v-v-v  (voiced fricative)","vvvvv","Buzz 'v' sound for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
            ]),
            _lvl("lvl_vwu_adv","task_vocal_warmup","advanced",3,[
                _p("p_vwu_adv_01","Hum a simple melody for 10 seconds.",None,"Hum any simple tune:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=10),
                _p("p_vwu_adv_02","Siren on /a/ up and down twice.",None,"Full siren — /a/ — up and down:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=10),
                _p("p_vwu_adv_03","Hello, my name is ___. (with warmed-up voice)","Hello, my name is ___","Use your warmed-up voice to greet:",scope="sentence",task_type="voice"),
            ]),
        ],
    },

    {
        "task_id": "task_resonant_voice",
        "name": "Resonant voice therapy",
        "type": "voice", "task_mode": "repeat",
        "description": "Produce voice with easy, forward-focused resonance to reduce vocal fold impact stress.",
        "wpm_category": "word", "weight_category": "voice",
        "scoring_notes": "CS primary — captures vocal quality ease; PA secondary",
        "defect_mappings": _dm("task_resonant_voice",
            "defect_vocnod_child","defect_vocnod_adult","defect_spasdys_adult"),
        "levels": [
            _lvl("lvl_rvt_beg","task_resonant_voice","beginner",1,[
                _p("p_rvt_beg_01","mmm-ONE","mmm-one","Say 'mmm' then slide to 'one' — feel buzzing on lips:",scope="word",task_type="voice"),
                _p("p_rvt_beg_02","mmm-MO","mmm-mo","Resonant 'mo' — buzzing forward:",scope="word",task_type="voice"),
                _p("p_rvt_beg_03","mmm-ME","mmm-me","Resonant 'me' — forward buzz:",scope="word",task_type="voice"),
            ]),
            _lvl("lvl_rvt_int","task_resonant_voice","intermediate",2,[
                _p("p_rvt_int_01","My name is ___","My name is ___","Say with resonant, forward voice:",scope="sentence",task_type="voice"),
                _p("p_rvt_int_02","More and more.","More and more.","Resonant voice — feel the forward buzz:",scope="sentence",task_type="voice"),
                _p("p_rvt_int_03","Hello. How are you?","Hello. How are you?","Greet with easy resonant voice:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_rvt_adv","task_resonant_voice","advanced",3,[
                _p("p_rvt_adv_01","I am ready to meet everyone today.","I am ready to meet everyone today.","Use resonant voice throughout:",scope="sentence",task_type="voice"),
                _p("p_rvt_adv_02","Tell me about your morning — use resonant voice.",None,"Speak for 20 seconds with resonant technique:",scope="discourse",task_type="voice",tc_mode="duration",target_dur=20,min_words=12),
                _p("p_rvt_adv_03","Many magnificent mountains make majestic views.","Many magnificent mountains make majestic views.","Read with resonant, forward-placed voice:",scope="sentence",task_type="voice"),
            ]),
        ],
    },

    {
        "task_id": "task_vocal_pacing",
        "name": "Vocal pacing and breath support",
        "type": "voice", "task_mode": "read_aloud",
        "description": "Match breath groups to sentence length with good vocal support to improve projection and endurance.",
        "wpm_category": "sentence", "weight_category": "voice",
        "scoring_notes": "SRS and CS measure breath pacing; FS captures fluency of breath management",
        "defect_mappings": _dm("task_vocal_pacing",
            "defect_vocnod_child","defect_vcpar_adult","defect_spasdys_adult"),
        "levels": [
            _lvl("lvl_vpc_beg","task_vocal_pacing","beginner",1,[
                _p("p_vpc_beg_01","I am here. [breathe] I am ready.","I am here. I am ready.","Take a breath between the two sentences:",scope="sentence",task_type="voice"),
                _p("p_vpc_beg_02","One. Two. Three. [breathe] Four. Five.","One. Two. Three. Four. Five.","Breathe at the marked point:",scope="sentence",task_type="voice"),
                _p("p_vpc_beg_03","Hello. [breathe] My name is ___. [breathe] Nice to meet you.","Hello. My name is ___. Nice to meet you.","Breathe between each sentence:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_vpc_int","task_vocal_pacing","intermediate",2,[
                _p("p_vpc_int_01","Good morning, everyone. [breath] I am glad to be here today.","Good morning, everyone. I am glad to be here today.","Read — breathe at the mark:",scope="sentence",task_type="voice"),
                _p("p_vpc_int_02","The weather today is mild and sunny. [breath] Perfect for a walk.",
                   "The weather today is mild and sunny. Perfect for a walk.","Breathe where marked:",scope="sentence",task_type="voice"),
                _p("p_vpc_int_03","I would like to tell you about my week. [breath] Several interesting things happened.",
                   "I would like to tell you about my week. Several interesting things happened.","Read with breath support:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_vpc_adv","task_vocal_pacing","advanced",3,[
                _p("p_vpc_adv_01","The annual report covered three main areas: finance, operations, and strategy.",
                   "The annual report covered three main areas: finance, operations, and strategy.",
                   "Read at a measured pace with good breath support:",scope="sentence",task_type="voice"),
                _p("p_vpc_adv_02","Describe your typical morning routine — use breath support throughout.",None,
                   "Speak for 30 seconds with controlled breath support:",scope="discourse",task_type="voice",tc_mode="duration",target_dur=30,min_words=20),
                _p("p_vpc_adv_03","She carefully considered all her options before making a final decision.",
                   "She carefully considered all her options before making a final decision.","Read clearly with breath pacing:",scope="sentence",task_type="voice"),
            ]),
        ],
    },

    {
        "task_id": "task_pitch_prosody",
        "name": "Pitch range and prosodic variation",
        "type": "voice", "task_mode": "repeat",
        "description": "Expand pitch range and restore prosodic variation through modelled imitation.",
        "wpm_category": "sentence", "weight_category": "voice",
        "scoring_notes": "CS and FS capture prosodic richness; SRS monitors rate",
        "defect_mappings": _dm("task_pitch_prosody",
            "defect_vocnod_child","defect_reson_child","defect_vocnod_adult",
            "defect_vcpar_adult","defect_spasdys_adult","defect_hypodys_adult"),
        "levels": [
            _lvl("lvl_ppr_beg","task_pitch_prosody","beginner",1,[
                _p("p_ppr_beg_01","Is it ready? (rising)","Is it ready?","Say with a rising question intonation:",scope="sentence",task_type="voice"),
                _p("p_ppr_beg_02","Yes, it is! (high excited pitch)","Yes, it is!","Use high, animated pitch:",scope="sentence",task_type="voice"),
                _p("p_ppr_beg_03","Oh no. (low falling pitch)","Oh no.","Use a low, falling pitch:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_ppr_int","task_pitch_prosody","intermediate",2,[
                _p("p_ppr_int_01","Really? Are you sure?","Really? Are you sure?","Express surprise — varied pitch:",scope="sentence",task_type="voice"),
                _p("p_ppr_int_02","That is AMAZING news!","That is AMAZING news!","Emphasise 'amazing' with high pitch:",scope="sentence",task_type="voice"),
                _p("p_ppr_int_03","I said MONDAY, not Tuesday.","I said MONDAY, not Tuesday.","Contrastive stress — high pitch on Monday:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_ppr_adv","task_pitch_prosody","advanced",3,[
                _p("p_ppr_adv_01","Good morning everyone! I am very pleased to be here today.",
                   "Good morning everyone! I am very pleased to be here today.",
                   "Read with varied, expressive pitch:",scope="sentence",task_type="voice"),
                _p("p_ppr_adv_02","Tell me an exciting story — use your full pitch range.",None,
                   "Tell a story with lots of pitch variation:",scope="discourse",task_type="voice",tc_mode="duration",target_dur=30,min_words=20),
                _p("p_ppr_adv_03","The announcement was met with shock, then disbelief, and finally anger.",
                   "The announcement was met with shock, then disbelief, and finally anger.",
                   "Read with appropriate emotional prosody:",scope="sentence",task_type="voice"),
            ]),
        ],
    },

    {
        "task_id": "task_loudness_projection",
        "name": "Loudness and vocal projection",
        "type": "voice", "task_mode": "repeat",
        "description": "Practise increasing and projecting voice volume to improve functional communication loudness.",
        "wpm_category": "sentence", "weight_category": "voice",
        "scoring_notes": "CS and SRS measure loudness and control; FS captures stability",
        "defect_mappings": _dm("task_loudness_projection",
            "defect_dysart_adult","defect_vocnod_adult","defect_vcpar_adult","defect_hypodys_adult"),
        "levels": [
            _lvl("lvl_lpr_beg","task_loudness_projection","beginner",1,[
                _p("p_lpr_beg_01","HELLO","HELLO","Say loudly and clearly — project to the far wall:",scope="word",task_type="voice"),
                _p("p_lpr_beg_02","YES","YES","Say loudly:",scope="word",task_type="voice"),
                _p("p_lpr_beg_03","GOOD MORNING","GOOD MORNING","Project your voice loudly:",scope="word",task_type="voice"),
            ]),
            _lvl("lvl_lpr_int","task_loudness_projection","intermediate",2,[
                _p("p_lpr_int_01","I AM READY TO START.","I AM READY TO START.","Say loudly — project clearly:",scope="sentence",task_type="voice"),
                _p("p_lpr_int_02","HELLO, CAN YOU HEAR ME?","HELLO, CAN YOU HEAR ME?","Project to fill the room:",scope="sentence",task_type="voice"),
                _p("p_lpr_int_03","THE TRAIN LEAVES AT NINE.","THE TRAIN LEAVES AT NINE.","Say loudly and clearly:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_lpr_adv","task_loudness_projection","advanced",3,[
                _p("p_lpr_adv_01","Good afternoon, ladies and gentlemen.",
                   "Good afternoon, ladies and gentlemen.",
                   "Project as if addressing an audience:",scope="sentence",task_type="voice"),
                _p("p_lpr_adv_02","I would like to welcome you all here today.",
                   "I would like to welcome you all here today.",
                   "Loud clear projection:",scope="sentence",task_type="voice"),
                _p("p_lpr_adv_03","Tell me about your week — speak loudly and clearly throughout.",None,
                   "Sustain loud projection for 25 seconds:",scope="discourse",task_type="voice",tc_mode="duration",target_dur=25,min_words=15),
            ]),
        ],
    },

    {
        "task_id": "task_max_phonation_time",
        "name": "Maximum phonation time (MPT)",
        "type": "voice", "task_mode": "spontaneous",
        "description": "Sustain a vowel for as long as possible to measure and extend vocal fold efficiency.",
        "wpm_category": "phoneme", "weight_category": "voice",
        "scoring_notes": "Duration is the primary metric; CS captures voice quality during sustained phonation",
        "defect_mappings": _dm("task_max_phonation_time",
            "defect_vcpar_adult","defect_hypodys_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_mpt_beg","task_max_phonation_time","beginner",1,[
                _p("p_mpt_beg_01","ahhh  (sustain for 5 seconds)","ahh","Take a breath and hold /a/ for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
                _p("p_mpt_beg_02","ohhh  (sustain for 5 seconds)","ohh","Hold /o/ for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
                _p("p_mpt_beg_03","eee  (sustain for 5 seconds)","eee","Hold /e/ for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
            ]),
            _lvl("lvl_mpt_int","task_max_phonation_time","intermediate",2,[
                _p("p_mpt_int_01","ahhh  (sustain for 8 seconds)","ahh","Hold /a/ for 8 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=8),
                _p("p_mpt_int_02","sss  (sustain for 8 seconds)","sss","Hold /s/ for 8 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=8),
                _p("p_mpt_int_03","zzz  (sustain for 8 seconds)","zzz","Hold /z/ for 8 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=8),
            ]),
            _lvl("lvl_mpt_adv","task_max_phonation_time","advanced",3,[
                _p("p_mpt_adv_01","ahhh  (maximum — as long as possible)","ahh","Take a deep breath and hold /a/ as long as possible:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=15),
                _p("p_mpt_adv_02","eee  (maximum)","eee","Hold /e/ as long as possible:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=15),
                _p("p_mpt_adv_03","I AM… (sustain 'I' then continue the sentence)",None,"Begin 'I AM' and sustain voice into a full sentence:",scope="sentence",task_type="voice",tc_mode="duration",target_dur=12),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # MOTOR SPEECH TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_ddk_drill",
        "name": "Diadochokinesis (DDK) drill",
        "type": "motor_speech", "task_mode": "repeat",
        "description": "Rapid syllable repetition (pa-ta-ka) to measure and improve articulatory speed and coordination.",
        "wpm_category": "phoneme", "weight_category": "motor_speech",
        "scoring_notes": "PA and SRS both critical; consistency across the sequence is the key metric",
        "defect_mappings": _dm("task_ddk_drill",
            "defect_cas_child","defect_neurstut_adult","defect_aos_adult",
            "defect_hypodys_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_ddk_beg","task_ddk_drill","beginner",1,[
                _p("p_ddk_beg_01","pa  pa  pa  pa  pa","pa pa pa pa pa","Repeat /pa/ as quickly and clearly as possible:",scope="phoneme",phonemes=["/p/","/æ/"]),
                _p("p_ddk_beg_02","ta  ta  ta  ta  ta","ta ta ta ta ta","Repeat /ta/ quickly and evenly:",scope="phoneme",phonemes=["/t/","/æ/"]),
                _p("p_ddk_beg_03","ka  ka  ka  ka  ka","ka ka ka ka ka","Repeat /ka/ quickly:",scope="phoneme",phonemes=["/k/","/æ/"]),
            ]),
            _lvl("lvl_ddk_int","task_ddk_drill","intermediate",2,[
                _p("p_ddk_int_01","pa-ta  pa-ta  pa-ta","pa-ta pa-ta pa-ta","Alternate /pa-ta/ quickly:",scope="phoneme"),
                _p("p_ddk_int_02","ta-ka  ta-ka  ta-ka","ta-ka ta-ka ta-ka","Alternate /ta-ka/ quickly:",scope="phoneme"),
                _p("p_ddk_int_03","pa-ka  pa-ka  pa-ka","pa-ka pa-ka pa-ka","Alternate /pa-ka/:",scope="phoneme"),
            ]),
            _lvl("lvl_ddk_adv","task_ddk_drill","advanced",3,[
                _p("p_ddk_adv_01","pa-ta-ka  pa-ta-ka  pa-ta-ka","pa-ta-ka pa-ta-ka pa-ta-ka","Say as quickly as possible for 5 seconds:",scope="phoneme",tc_mode="duration",target_dur=5),
                _p("p_ddk_adv_02","ka-ta-pa  ka-ta-pa  ka-ta-pa","ka-ta-pa ka-ta-pa ka-ta-pa","Reverse order — as fast as possible:",scope="phoneme",tc_mode="duration",target_dur=5),
                _p("p_ddk_adv_03","pa-ta-ka-pa-ta-ka (continuous)","pa-ta-ka continuous","Continuous sequence for 8 seconds:",scope="phoneme",tc_mode="duration",target_dur=8),
            ]),
        ],
    },

    {
        "task_id": "task_integral_stimulation",
        "name": "Integral stimulation — watch, listen, say",
        "type": "motor_speech", "task_mode": "imitate",
        "description": "Imitate modelled speech using simultaneous and then independent production (DEVA: Do it with me / for me).",
        "wpm_category": "word", "weight_category": "motor_speech",
        "scoring_notes": "PA is primary — close match to model is the therapeutic goal",
        "defect_mappings": _dm("task_integral_stimulation",
            "defect_cas_child","defect_dysart_adult","defect_aos_adult"),
        "levels": [
            _lvl("lvl_ist_beg","task_integral_stimulation","beginner",1,[
                _p("p_ist_beg_01","mama","mama","Watch and listen — then say exactly the same way:",scope="word"),
                _p("p_ist_beg_02","bye-bye","bye-bye","Imitate precisely:",scope="word"),
                _p("p_ist_beg_03","no  no","no  no","Imitate:",scope="word"),
            ]),
            _lvl("lvl_ist_int","task_integral_stimulation","intermediate",2,[
                _p("p_ist_int_01","I want that.","I want that.","Imitate the phrase exactly:",scope="sentence"),
                _p("p_ist_int_02","Can I have some?","Can I have some?","Imitate clearly:",scope="sentence"),
                _p("p_ist_int_03","Stop it please.","Stop it please.","Imitate the phrase:",scope="sentence"),
            ]),
            _lvl("lvl_ist_adv","task_integral_stimulation","advanced",3,[
                _p("p_ist_adv_01","I would like a glass of water please.",
                   "I would like a glass of water please.","Imitate the full sentence:",scope="sentence"),
                _p("p_ist_adv_02","The weather is nice today.","The weather is nice today.","Imitate then say independently:",scope="sentence"),
                _p("p_ist_adv_03","Good morning, how are you feeling today?",
                   "Good morning, how are you feeling today?","Imitate then produce independently:",scope="sentence"),
            ]),
        ],
    },

    {
        "task_id": "task_progressive_complexity",
        "name": "Progressive articulatory complexity (CAS / AOS)",
        "type": "motor_speech", "task_mode": "repeat",
        "description": "Systematically increase motor complexity from CV syllables to multisyllabic words to sentences.",
        "wpm_category": "word", "weight_category": "motor_speech",
        "scoring_notes": "PA primary — consistency is more important than speed in early stages",
        "defect_mappings": _dm("task_progressive_complexity","defect_cas_child","defect_aos_adult"),
        "levels": [
            _lvl("lvl_pco_beg","task_progressive_complexity","beginner",1,[
                _p("p_pco_beg_01","me  me  me","me","Repeat three times consistently:",scope="word"),
                _p("p_pco_beg_02","go  go  go","go","Repeat consistently:",scope="word"),
                _p("p_pco_beg_03","no  no  no","no","Same each time:",scope="word"),
            ]),
            _lvl("lvl_pco_int","task_progressive_complexity","intermediate",2,[
                _p("p_pco_int_01","butter  butter  butter","butter","Repeat consistently:",scope="word"),
                _p("p_pco_int_02","table  table  table","table","Repeat consistently:",scope="word"),
                _p("p_pco_int_03","banana  banana  banana","banana","Three consistent productions:",scope="word"),
            ]),
            _lvl("lvl_pco_adv","task_progressive_complexity","advanced",3,[
                _p("p_pco_adv_01","I want a banana.","I want a banana.","Produce consistently:",scope="sentence"),
                _p("p_pco_adv_02","The butterfly landed gently.","The butterfly landed gently.","Produce the sentence consistently:",scope="sentence"),
                _p("p_pco_adv_03","Gradually increasing difficulty.","Gradually increasing difficulty.","Produce the complex sentence:",scope="sentence"),
            ]),
        ],
    },

    {
        "task_id": "task_contrastive_stress",
        "name": "Contrastive stress production",
        "type": "motor_speech", "task_mode": "repeat",
        "description": "Produce sentences with varying stress patterns to restore prosodic flexibility in motor speech disorders.",
        "wpm_category": "sentence", "weight_category": "motor_speech",
        "scoring_notes": "PA and FS capture precision and prosodic accuracy",
        "defect_mappings": _dm("task_contrastive_stress",
            "defect_aos_adult","defect_hypodys_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_cst_beg","task_contrastive_stress","beginner",1,[
                _p("p_cst_beg_01","BIG dog (not small dog)","BIG dog","Stress 'BIG' loudly — other words softer:",scope="sentence",task_type="motor_speech"),
                _p("p_cst_beg_02","RED ball (not blue ball)","RED ball","Stress 'RED':",scope="sentence",task_type="motor_speech"),
                _p("p_cst_beg_03","I want IT (not that)","I want IT","Stress 'IT':",scope="sentence",task_type="motor_speech"),
            ]),
            _lvl("lvl_cst_int","task_contrastive_stress","intermediate",2,[
                _p("p_cst_int_01","I want COFFEE, not tea.","I want COFFEE, not tea.","Stress the target word:",scope="sentence",task_type="motor_speech"),
                _p("p_cst_int_02","She went to the SHOP, not the park.","She went to the SHOP, not the park.","Stress the contrasted word:",scope="sentence",task_type="motor_speech"),
                _p("p_cst_int_03","HE did it, not me.","HE did it, not me.","Contrastive stress on 'HE':",scope="sentence",task_type="motor_speech"),
            ]),
            _lvl("lvl_cst_adv","task_contrastive_stress","advanced",3,[
                _p("p_cst_adv_01","I said I wanted to LEAVE, not to STAY.",
                   "I said I wanted to LEAVE, not to STAY.","Read with strong contrastive stress:",scope="sentence",task_type="motor_speech"),
                _p("p_cst_adv_02","The BLUE car hit the RED wall, not the white one.",
                   "The BLUE car hit the RED wall, not the white one.","Stress each marked word:",scope="sentence",task_type="motor_speech"),
                _p("p_cst_adv_03","She chose the LARGER piece, not the smaller one.",
                   "She chose the LARGER piece, not the smaller one.","Appropriate stress throughout:",scope="sentence",task_type="motor_speech"),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SOCIAL COMMUNICATION TASKS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_greetings_intros",
        "name": "Greetings and introductions",
        "type": "language", "task_mode": "answer",
        "description": "Practise scripted social openers and self-introductions in a structured, low-anxiety format.",
        "wpm_category": "conversation", "weight_category": "social_communication",
        "scoring_notes": "WA and CS capture social language accuracy and confidence",
        "defect_mappings": _dm("task_greetings_intros","defect_asd_child","defect_mute_child"),
        "levels": [
            _lvl("lvl_gri_beg","task_greetings_intros","beginner",1,[
                _p("p_gri_beg_01","Hello.","Hello.","Say 'Hello' to greet:",scope="word",task_type="social_communication"),
                _p("p_gri_beg_02","My name is ___.",None,"Say your name:",scope="word",task_type="social_communication",tc_mode="completion"),
                _p("p_gri_beg_03","How are you? / I am fine.",None,"Say the greeting exchange:",scope="word",task_type="social_communication"),
            ]),
            _lvl("lvl_gri_int","task_greetings_intros","intermediate",2,[
                _p("p_gri_int_01","Hello! My name is ___. Nice to meet you.",None,
                   "Give a full introduction:",scope="sentence",task_type="social_communication",tc_mode="word_count",target_wc=12,min_words=6),
                _p("p_gri_int_02","Good morning! How are you today?","Good morning! How are you today?",
                   "Greet warmly:",scope="sentence",task_type="social_communication"),
                _p("p_gri_int_03","Hi, I'm ___. I'm in year ___. I like ___.","Hi, I'm ___.",
                   "Introduce yourself fully:",scope="sentence",task_type="social_communication",tc_mode="word_count",target_wc=15,min_words=8),
            ]),
            _lvl("lvl_gri_adv","task_greetings_intros","advanced",3,[
                _p("p_gri_adv_01","Introduce yourself as if meeting a new classmate.",None,
                   "Full introduction — name, age, one interest:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=20,min_words=15),
                _p("p_gri_adv_02","Greet a teacher you have not met before.",None,
                   "Formal greeting and introduction:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=20,min_words=12),
                _p("p_gri_adv_03","You are at a birthday party — greet the host.",None,
                   "Greet appropriately for the situation:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=20,min_words=10),
            ]),
        ],
    },

    {
        "task_id": "task_topic_maintenance",
        "name": "Topic maintenance in conversation",
        "type": "language", "task_mode": "answer",
        "description": "Practise staying on topic and adding relevant information to a conversational topic.",
        "wpm_category": "conversation", "weight_category": "social_communication",
        "scoring_notes": "WA and FS capture relevance and coherence of contributions",
        "defect_mappings": _dm("task_topic_maintenance","defect_asd_child","defect_mute_child"),
        "levels": [
            _lvl("lvl_top_beg","task_topic_maintenance","beginner",1,[
                _p("p_top_beg_01","We are talking about animals. Say one thing about animals.",None,
                   "Stay on the topic of animals:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=8,min_words=4),
                _p("p_top_beg_02","We are talking about food. Say one thing you like to eat.",None,
                   "Stay on the topic:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=8,min_words=4),
                _p("p_top_beg_03","We are talking about the weather. Say one thing about today's weather.",None,
                   "Stay on the topic:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=8,min_words=4),
            ]),
            _lvl("lvl_top_int","task_topic_maintenance","intermediate",2,[
                _p("p_top_int_01","Tell me two things about your school.",None,
                   "Stay on the topic of school — two relevant facts:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=20,min_words=10),
                _p("p_top_int_02","We are talking about sports. Tell me about a sport you like.",None,
                   "Two or three sentences about the sport:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=25,min_words=12),
                _p("p_top_int_03","We are talking about family. Tell me about someone in your family.",None,
                   "Stay on topic — describe one family member:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=25,min_words=12),
            ]),
            _lvl("lvl_top_adv","task_topic_maintenance","advanced",3,[
                _p("p_top_adv_01","We are talking about films. Tell me about a film you have seen and why you liked it.",None,
                   "Stay on topic — film summary and opinion:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=35,min_words=25),
                _p("p_top_adv_02","We are talking about future plans. What do you want to do in the next year?",None,
                   "Stay on topic — future plans:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=35,min_words=25),
                _p("p_top_adv_03","We are talking about hobbies. Describe your main hobby in detail.",None,
                   "Maintain the topic throughout:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=40,min_words=30),
            ]),
        ],
    },

    {
        "task_id": "task_perspective_taking",
        "name": "Perspective-taking and emotion labelling",
        "type": "language", "task_mode": "answer",
        "description": "Identify and label emotions of others in social scenarios to build theory of mind and empathy.",
        "wpm_category": "spontaneous", "weight_category": "social_communication",
        "scoring_notes": "WA captures accuracy of emotion labels; CS reflects confidence",
        "defect_mappings": _dm("task_perspective_taking","defect_asd_child"),
        "levels": [
            _lvl("lvl_per_beg","task_perspective_taking","beginner",1,[
                _p("p_per_beg_01","child crying","sad","Look at the picture — how does this child feel?",scope="word",task_type="social_communication"),
                _p("p_per_beg_02","child laughing","happy","How does this child feel?",scope="word",task_type="social_communication"),
                _p("p_per_beg_03","child looking scared","scared","How does this child feel?",scope="word",task_type="social_communication"),
            ]),
            _lvl("lvl_per_int","task_perspective_taking","intermediate",2,[
                _p("p_per_int_01","Your friend dropped their ice cream. How do they feel? Why?",None,
                   "Say how they feel and one reason why:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=12,min_words=6),
                _p("p_per_int_02","Your friend got a new puppy. How do they feel? Why?",None,
                   "Emotion and reason:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=12,min_words=6),
                _p("p_per_int_03","A child is left out of a game. How do they feel? What should you do?",None,
                   "Emotion plus appropriate response:",scope="discourse",task_type="social_communication",tc_mode="word_count",target_wc=15,min_words=8),
            ]),
            _lvl("lvl_per_adv","task_perspective_taking","advanced",3,[
                _p("p_per_adv_01","If you said something unkind by accident, how would your friend feel? What would you do?",None,
                   "Full response — emotion and action:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=25,min_words=15),
                _p("p_per_adv_02","Imagine a classmate is new and has no friends yet. How might they feel? What could you do to help?",None,
                   "Perspective and empathic response:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=25,min_words=15),
                _p("p_per_adv_03","Your friend tells you their pet has died. What do they feel? What would be a kind thing to say?",None,
                   "Emotional understanding and social response:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=25,min_words=15),
            ]),
        ],
    },

    {
        "task_id": "task_asking_help",
        "name": "Asking for help pragmatically",
        "type": "language", "task_mode": "answer",
        "description": "Practise forming and expressing polite, contextually appropriate requests for help.",
        "wpm_category": "conversation", "weight_category": "social_communication",
        "scoring_notes": "WA primary — target request language must be produced; CS captures confidence",
        "defect_mappings": _dm("task_asking_help","defect_asd_child","defect_mute_child"),
        "levels": [
            _lvl("lvl_ash_beg","task_asking_help","beginner",1,[
                _p("p_ash_beg_01","Help please.","Help please.","Say these words:",scope="word",task_type="social_communication"),
                _p("p_ash_beg_02","Can you help me?","Can you help me?","Say the request:",scope="word",task_type="social_communication"),
                _p("p_ash_beg_03","I need help.","I need help.","Say the phrase:",scope="word",task_type="social_communication"),
            ]),
            _lvl("lvl_ash_int","task_asking_help","intermediate",2,[
                _p("p_ash_int_01","Excuse me, can you help me please?","Excuse me, can you help me please?","Ask politely:",scope="sentence",task_type="social_communication"),
                _p("p_ash_int_02","I don't understand. Can you explain?","I don't understand. Can you explain?","Say the request:",scope="sentence",task_type="social_communication"),
                _p("p_ash_int_03","Could you show me where the library is?","Could you show me where the library is?","Ask for directions politely:",scope="sentence",task_type="social_communication"),
            ]),
            _lvl("lvl_ash_adv","task_asking_help","advanced",3,[
                _p("p_ash_adv_01","You don't understand your homework. Ask your teacher for help.",None,
                   "Role-play — ask your teacher politely:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=15,min_words=10),
                _p("p_ash_adv_02","You need help in a shop — the item you want is on a high shelf.",None,
                   "Ask a shop assistant for help:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=15,min_words=10),
                _p("p_ash_adv_03","You feel unwell at school. Tell an adult how you are feeling and ask for help.",None,
                   "Explain how you feel and ask for help:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=20,min_words=12),
            ]),
        ],
    },

    {
        "task_id": "task_confident_speaking",
        "name": "Confident and assertive speaking",
        "type": "language", "task_mode": "spontaneous",
        "description": "Graduated vocal confidence exercises — from whispered to full voiced speech in increasingly challenging contexts.",
        "wpm_category": "conversation", "weight_category": "social_communication",
        "scoring_notes": "CS and FS primary — confidence level and vocal quality are targets",
        "defect_mappings": _dm("task_confident_speaking","defect_mute_child","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_csp_beg","task_confident_speaking","beginner",1,[
                _p("p_csp_beg_01","hello","hello","Whisper 'hello':",scope="word",task_type="social_communication"),
                _p("p_csp_beg_02","yes","yes","Say 'yes' in a quiet voice:",scope="word",task_type="social_communication"),
                _p("p_csp_beg_03","My name is ___.",None,"Say your name quietly:",scope="word",task_type="social_communication",tc_mode="completion"),
            ]),
            _lvl("lvl_csp_int","task_confident_speaking","intermediate",2,[
                _p("p_csp_int_01","My name is ___.",None,"Say your name in a normal voice:",scope="sentence",task_type="social_communication"),
                _p("p_csp_int_02","I like ___.",None,"Say one thing you like:",scope="sentence",task_type="social_communication",tc_mode="word_count",target_wc=8,min_words=3),
                _p("p_csp_int_03","I am here today.","I am here today.","Say with a confident, clear voice:",scope="sentence",task_type="social_communication"),
            ]),
            _lvl("lvl_csp_adv","task_confident_speaking","advanced",3,[
                _p("p_csp_adv_01","My name is ___. I like ___.",None,
                   "Confident introduction — name and one fact about you:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=15,min_words=10),
                _p("p_csp_adv_02","My favourite season is ___. because ___.",None,
                   "State your opinion clearly and confidently:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=20,min_words=12),
                _p("p_csp_adv_03","Can I join in?","Can I join in?",
                   "Say the question with a clear, confident voice:",scope="discourse",task_type="social_communication",tc_mode="duration",target_dur=15,min_words=8),
            ]),
        ],
    },

    {
        "task_id": "task_vegetative_phonation",
        "name": "Vegetative phonation — push-pull effort",
        "type": "voice", "task_mode": "spontaneous",
        "description": "Use push-pull effort techniques to initiate and sustain phonation for paralytic dysphonia.",
        "wpm_category": "phoneme", "weight_category": "voice",
        "scoring_notes": "CS measures voice onset quality; duration of sustained phonation is primary",
        "defect_mappings": _dm("task_vegetative_phonation","defect_vcpar_adult","defect_spasdys_adult"),
        "levels": [
            _lvl("lvl_vph_beg","task_vegetative_phonation","beginner",1,[
                _p("p_vph_beg_01","Push down on the table and say 'ahhh'.",None,
                   "Push down firmly — voice comes through:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=3),
                _p("p_vph_beg_02","Pull up on the chair seat and say 'eee'.",None,
                   "Pull up — let the voice come through:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=3),
                _p("p_vph_beg_03","Push hands together firmly — say 'oh'.",None,
                   "Press hands — voice on 'oh':",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=3),
            ]),
            _lvl("lvl_vph_int","task_vegetative_phonation","intermediate",2,[
                _p("p_vph_int_01","Push and hold 'ahhh' for 5 seconds.","ahh","Push effort — sustain voice for 5 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=5),
                _p("p_vph_int_02","Push and say 'one — two — three'.",None,"Push effort — count to three:",scope="word",task_type="voice"),
                _p("p_vph_int_03","Push effort — say 'hello'.",None,"Push and produce 'hello':",scope="word",task_type="voice"),
            ]),
            _lvl("lvl_vph_adv","task_vegetative_phonation","advanced",3,[
                _p("p_vph_adv_01","Using push effort — say your full name.",None,
                   "Push effort — say your name clearly:",scope="sentence",task_type="voice"),
                _p("p_vph_adv_02","Say 'Good morning' with push effort.",None,
                   "Push effort greeting:",scope="sentence",task_type="voice"),
                _p("p_vph_adv_03","Use push effort — say a short sentence about yourself.",None,
                   "Push effort — any sentence about you:",scope="sentence",task_type="voice",tc_mode="word_count",target_wc=8,min_words=4),
            ]),
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SUPPLEMENTARY TASKS (bring total to ≥ 50)
    # ══════════════════════════════════════════════════════════════════════════

    {
        "task_id": "task_syllable_drill",
        "name": "Syllable-level production drill",
        "type": "motor_speech", "task_mode": "repeat",
        "description": "Systematic syllable repetition to establish consistent motor programmes for target CV and CVC shapes.",
        "wpm_category": "phoneme", "weight_category": "motor_speech",
        "scoring_notes": "PA primary — each syllable scored for articulatory precision and consistency",
        "defect_mappings": _dm("task_syllable_drill",
            "defect_cas_child","defect_dysart_adult","defect_aos_adult",
            "defect_hypodys_adult","defect_spastdys_adult"),
        "levels": [
            _lvl("lvl_syl_beg","task_syllable_drill","beginner",1,[
                _p("p_syl_beg_01","ma ma ma","ma ma ma","Repeat the syllable sequence:",scope="phoneme",task_type="motor_speech",phonemes=["/m/"],position="word_initial"),
                _p("p_syl_beg_02","pa pa pa","pa pa pa","Repeat clearly:",scope="phoneme",task_type="motor_speech",phonemes=["/p/"],position="word_initial"),
                _p("p_syl_beg_03","ta ta ta","ta ta ta","Repeat at an even pace:",scope="phoneme",task_type="motor_speech",phonemes=["/t/"],position="word_initial"),
            ]),
            _lvl("lvl_syl_int","task_syllable_drill","intermediate",2,[
                _p("p_syl_int_01","ma ma ma — ba ba ba","ma ma ma — ba ba ba","Alternate the syllable pairs:",scope="phoneme",task_type="motor_speech",phonemes=["/m/","/b/"],position="word_initial"),
                _p("p_syl_int_02","pa ta ka","pa ta ka","Repeat the DDK sequence three times:",scope="phoneme",task_type="motor_speech",phonemes=["/p/","/t/","/k/"],position="word_initial"),
                _p("p_syl_int_03","tip top tap","tip top tap","Say each word at a steady pace:",scope="word",task_type="motor_speech",phonemes=["/t/"],position="word_initial"),
            ]),
            _lvl("lvl_syl_adv","task_syllable_drill","advanced",3,[
                _p("p_syl_adv_01","pataka pataka pataka","pataka pataka pataka","Repeat the full DDK sequence:",scope="phoneme",task_type="motor_speech",phonemes=["/p/","/t/","/k/"],position="word_initial"),
                _p("p_syl_adv_02","buttercup — butterfly — butter","buttercup — butterfly — butter","Say each word precisely:",scope="word",task_type="motor_speech"),
                _p("p_syl_adv_03","Peter Piper picked a peck.","Peter Piper picked a peck.","Read at a controlled pace:",scope="sentence",task_type="motor_speech",phonemes=["/p/"],position="word_initial"),
            ]),
        ],
    },

    {
        "task_id": "task_breath_support",
        "name": "Breath support for voice projection",
        "type": "voice", "task_mode": "spontaneous",
        "description": "Diaphragmatic breathing exercises to build respiratory support for sustained and projected voice.",
        "wpm_category": "phoneme", "weight_category": "voice",
        "scoring_notes": "CS measures breath-voice coordination; duration of sustained phonation tracks improvement",
        "defect_mappings": _dm("task_breath_support",
            "defect_hypodys_adult","defect_spastdys_adult","defect_vcpar_adult"),
        "levels": [
            _lvl("lvl_brs_beg","task_breath_support","beginner",1,[
                _p("p_brs_beg_01","ahhh","ahh","Take a deep breath, then sustain the vowel:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=3),
                _p("p_brs_beg_02","sss","sss","Breathe in, then produce a sustained /s/:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=3),
                _p("p_brs_beg_03","one two three","one two three","Breathe in, then count on one breath:",scope="word",task_type="voice"),
            ]),
            _lvl("lvl_brs_int","task_breath_support","intermediate",2,[
                _p("p_brs_int_01","ahhh","ahh","Sustain the vowel for 7 seconds on one breath:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=7),
                _p("p_brs_int_02","one two three four five","one two three four five","Count to five on a single breath:",scope="word",task_type="voice"),
                _p("p_brs_int_03","Good morning, everyone.","Good morning, everyone.","Project with a full breath:",scope="sentence",task_type="voice"),
            ]),
            _lvl("lvl_brs_adv","task_breath_support","advanced",3,[
                _p("p_brs_adv_01","ahhh","ahh","Sustain the vowel for 10 seconds:",scope="phoneme",task_type="voice",tc_mode="duration",target_dur=10),
                _p("p_brs_adv_02","The weather is warm and sunny today.","The weather is warm and sunny today.","Say the sentence with full breath support:",scope="sentence",task_type="voice"),
                _p("p_brs_adv_03","I can speak clearly and with confidence.",
                   "I can speak clearly and with confidence.",
                   "Project your voice — one steady breath:",scope="sentence",task_type="voice"),
            ]),
        ],
    },

    {
        "task_id": "task_voluntary_stuttering",
        "name": "Voluntary stuttering technique",
        "type": "fluency", "task_mode": "spontaneous",
        "description": "Intentionally produce controlled stutters to reduce avoidance, desensitise to disfluency, and increase speaker control.",
        "wpm_category": "fluency", "weight_category": "fluency",
        "scoring_notes": "FS primary — controlled voluntary stutter is the target; avoidance or rush = partial",
        "defect_mappings": _dm("task_voluntary_stuttering",
            "defect_devstut_child","defect_neurstut_adult","defect_psychdis_adult"),
        "levels": [
            _lvl("lvl_vst_beg","task_voluntary_stuttering","beginner",1,[
                _p("p_vst_beg_01","h-h-hello","hello","Intentionally stutter on the first sound:",scope="word",task_type="fluency"),
                _p("p_vst_beg_02","m-m-my name","my name","Voluntary stutter on the first word:",scope="word",task_type="fluency"),
                _p("p_vst_beg_03","g-g-good morning","good morning","Stutter intentionally, then complete the phrase:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_vst_int","task_voluntary_stuttering","intermediate",2,[
                _p("p_vst_int_01","I l-l-like to read books.","I like to read books.","Voluntary stutter on one word in the sentence:",scope="sentence",task_type="fluency"),
                _p("p_vst_int_02","T-t-today is a good day.","Today is a good day.","Stutter intentionally, then continue smoothly:",scope="sentence",task_type="fluency"),
                _p("p_vst_int_03","My f-f-favourite colour is blue.","My favourite colour is blue.","Stutter intentionally on the marked word:",scope="sentence",task_type="fluency"),
            ]),
            _lvl("lvl_vst_adv","task_voluntary_stuttering","advanced",3,[
                _p("p_vst_adv_01","Introduce yourself using a voluntary stutter on your name.",None,
                   "Introduce yourself — stutter intentionally then continue:",scope="discourse",task_type="fluency",tc_mode="duration",target_dur=15,min_words=8),
                _p("p_vst_adv_02","Talk about your weekend — stutter voluntarily at least twice.",None,
                   "Speak fluently with two voluntary stutters:",scope="discourse",task_type="fluency",tc_mode="duration",target_dur=20,min_words=12),
                _p("p_vst_adv_03","Tell me your address — using voluntary stuttering.",None,
                   "Voluntary stutter on each new piece of information:",scope="discourse",task_type="fluency",tc_mode="word_count",target_wc=15,min_words=8),
            ]),
        ],
    },

    {
        "task_id": "task_semantic_feature_analysis",
        "name": "Semantic feature analysis",
        "type": "language", "task_mode": "answer",
        "description": "Generate semantic features (category, function, location, appearance) to support word retrieval via indirect lexical access.",
        "wpm_category": "conversation", "weight_category": "language",
        "scoring_notes": "WA primary — target features must be produced; FS measures elaboration",
        "defect_mappings": _dm("task_semantic_feature_analysis",
            "defect_anomia_adult","defect_aphexpr_adult"),
        "levels": [
            _lvl("lvl_sfa_beg","task_semantic_feature_analysis","beginner",1,[
                _p("p_sfa_beg_01","apple","It is a fruit. It is red. You eat it.",
                   "Name the category and one feature of this item:",scope="word",task_type="language"),
                _p("p_sfa_beg_02","chair","It is furniture. You sit on it.",
                   "Name the category and one feature:",scope="word",task_type="language"),
                _p("p_sfa_beg_03","dog","It is an animal. It barks.",
                   "Name the category and one feature:",scope="word",task_type="language"),
            ]),
            _lvl("lvl_sfa_int","task_semantic_feature_analysis","intermediate",2,[
                _p("p_sfa_int_01","telephone",None,
                   "Say the category, where you find it, and what it does:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=6),
                _p("p_sfa_int_02","hammer",None,
                   "Describe: category, function, where you use it:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=6),
                _p("p_sfa_int_03","umbrella",None,
                   "Category, appearance, when you use it:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=15,min_words=6),
            ]),
            _lvl("lvl_sfa_adv","task_semantic_feature_analysis","advanced",3,[
                _p("p_sfa_adv_01","stethoscope",None,
                   "Give full semantic description — category, function, appearance, who uses it:",scope="discourse",task_type="language",tc_mode="word_count",target_wc=20,min_words=10),
                _p("p_sfa_adv_02","thermometer",None,
                   "Describe in detail — all semantic features you can name:",scope="discourse",task_type="language",tc_mode="duration",target_dur=20,min_words=10),
                _p("p_sfa_adv_03","ladder",None,
                   "Full semantic feature set — category, function, location, appearance:",scope="discourse",task_type="language",tc_mode="duration",target_dur=20,min_words=10),
            ]),
        ],
    },

]


# ─── BASELINES (30) ───────────────────────────────────────────────────────────

def _bitem(item_id, order, task_name, instruction, display, expected,
           formula_mode, target_phoneme=None, max_score=None,
           scoring_method="percentage_correct", scope=None,
           formula_weights=None, wpm_range=None, defect_codes=None,
           response_type="speech"):
    return {
        "item_id": item_id,
        "order_index": order,
        "task_name": task_name,
        "instruction": instruction,
        "display_content": display,
        "expected_output": expected,
        "response_type": response_type,
        "target_phoneme": target_phoneme,
        "formula_mode": formula_mode,
        "max_score": max_score,
        "scoring_method": scoring_method,
        "scope": scope,
        "formula_weights": json.dumps(formula_weights) if formula_weights else None,
        "wpm_range": json.dumps(wpm_range) if wpm_range else None,
        "defect_codes": json.dumps(defect_codes) if defect_codes else None,
    }


def _bsec(sec_id, name, instructions, order, target_defect_id, items):
    return {"section_id": sec_id, "section_name": name,
            "instructions": instructions, "order_index": order,
            "target_defect_id": target_defect_id, "items": items}


BASELINES = [

    {
        "baseline_id": "ba_phono_child", "code": "BAS_PHONO_CH",
        "name": "Phonological Disorder Baseline Assessment",
        "domain": "articulation", "administration_method": "automated",
        "description": "Structured baseline for phonological disorder — phoneme inventory probe and connected speech sample.",
        "defect_id": "defect_phono_child",
        "sections": [
            _bsec("bsec_phono_ch_1","Phoneme Inventory Probe","Assess accuracy of each error phoneme in isolation and at word level.",1,"defect_phono_child",[
                _bitem("bitem_phono_ch_01",1,"Phoneme isolation probe","Say each sound clearly: p, b, t, d, f, v, s, z, k, g","p b t d f v s z k g","p b t d f v s z k g","auto_phoneme_only",scope="phoneme",formula_weights={"pa":1.0}),
                _bitem("bitem_phono_ch_02",2,"Word-level phoneme probe","Say each word: sun, bus, cat, dog, fish, vine","sun bus cat dog fish vine","sun bus cat dog fish vine","auto_phoneme_only",scope="word",formula_weights={"pa":0.7,"wa":0.3}),
                _bitem("bitem_phono_ch_03",3,"Single word articulation test (20 words)","Name each picture clearly","(picture set: 20 target words)","(picture targets)","auto_phoneme_only",scope="word",wpm_range={"min":50,"max":90}),
            ]),
            _bsec("bsec_phono_ch_2","Connected Speech Sample","Assess phonological accuracy in continuous speech.",2,"defect_phono_child",[
                _bitem("bitem_phono_ch_04",1,"Sentence repetition","Repeat each sentence: 'The cat sat on the mat.' / 'Big blue birds fly fast.'","The cat sat on the mat. Big blue birds fly fast.","The cat sat on the mat. Big blue birds fly fast.","auto_phoneme_only",scope="sentence"),
                _bitem("bitem_phono_ch_05",2,"Clinician phonological process rating","Rate the presence and frequency of phonological processes","Clinician scores: fronting, cluster reduction, final consonant deletion","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",scope="phoneme",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_lisp_child", "code": "BAS_LISP_CH",
        "name": "Sibilant Lisp Baseline Assessment (Child)",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline assessment targeting /s/ and /z/ distortion in children.",
        "defect_id": "defect_lisp_child",
        "sections": [
            _bsec("bsec_lisp_ch_1","Sibilant Probe","Assess /s/ and /z/ accuracy across word positions.",1,"defect_lisp_child",[
                _bitem("bitem_lisp_ch_01",1,"Sibilant isolation","Hold each sound for 3 seconds: s / z","s  z","s z","auto_phoneme_only",target_phoneme="/s/,/z/",scope="phoneme",formula_weights={"pa":1.0}),
                _bitem("bitem_lisp_ch_02",2,"Sibilant word probe","Say each word: sun, bus, sister, scissors, zoo, buzz","sun bus sister scissors zoo buzz","sun bus sister scissors zoo buzz","auto_phoneme_only",target_phoneme="/s/,/z/",scope="word",formula_weights={"pa":0.7,"wa":0.3}),
                _bitem("bitem_lisp_ch_03",3,"Picture naming — 20 /s/ words","Name each picture (set of 20 /s/-initial, medial, final words)","(picture set)","(20 target words)","auto_phoneme_only",target_phoneme="/s/",scope="word"),
            ]),
            _bsec("bsec_lisp_ch_2","Connected Speech and Lisp Classification","Assess sibilant accuracy in sentences and clinician lisp type rating.",2,"defect_lisp_child",[
                _bitem("bitem_lisp_ch_04",1,"Clinician lisp type classification","Clinician rates: 1=interdental, 2=lateral, 3=mixed, 0=no lisp","(Clinician observation rating)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_rhot_child", "code": "BAS_RHOT_CH",
        "name": "Rhotacism Baseline Assessment (Child)",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline for /r/ distortion across word positions in children.",
        "defect_id": "defect_rhot_child",
        "sections": [
            _bsec("bsec_rhot_ch_1","/r/ Production Probe","Assess /r/ accuracy in isolation, syllables, and words.",1,"defect_rhot_child",[
                _bitem("bitem_rhot_ch_01",1,"/r/ isolation","Produce /r/ in isolation","r  ra  ri  ro","r ra ri ro","auto_phoneme_only",target_phoneme="/r/",scope="phoneme"),
                _bitem("bitem_rhot_ch_02",2,"/r/ word probe","Say: run, red, rabbit, car, star, river","run red rabbit car star river","run red rabbit car star river","auto_phoneme_only",target_phoneme="/r/",scope="word"),
                _bitem("bitem_rhot_ch_03",3,"Picture naming /r/ words (10 items)","Name each picture","(picture set: 10 /r/ words)","(10 target words)","auto_phoneme_only",target_phoneme="/r/",scope="word"),
            ]),
            _bsec("bsec_rhot_ch_2","Connected Speech","Assess /r/ in sentence context.",2,"defect_rhot_child",[
                _bitem("bitem_rhot_ch_04",1,"Clinician distortion type rating","Rate distortion: 1=derhotacised, 2=lateralised, 3=backed","(Clinician rates distortion type)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_front_child", "code": "BAS_FRONT_CH",
        "name": "Fronting Baseline Assessment (Child)",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline for velar fronting — /k/→/t/, /g/→/d/ substitution.",
        "defect_id": "defect_front_child",
        "sections": [
            _bsec("bsec_front_ch_1","Velar Production Probe","Assess /k/ and /g/ accuracy.",1,"defect_front_child",[
                _bitem("bitem_front_ch_01",1,"Velar isolation","Say: k / g / ka / ga","k g ka ga","k g ka ga","auto_phoneme_only",target_phoneme="/k/,/g/",scope="phoneme"),
                _bitem("bitem_front_ch_02",2,"Velar word probe","Say: key, cup, book, go, big, leg","key cup book go big leg","key cup book go big leg","auto_phoneme_only",target_phoneme="/k/,/g/",scope="word"),
                _bitem("bitem_front_ch_03",3,"Picture naming velars","Name 10 pictures with /k/ or /g/","(picture set)","(10 velar words)","auto_phoneme_only",target_phoneme="/k/,/g/",scope="word"),
            ]),
            _bsec("bsec_front_ch_2","Sentence Context","Assess fronting in connected speech.",2,"defect_front_child",[
                _bitem("bitem_front_ch_04",1,"Clinician fronting severity rating","Rate fronting frequency: 0=absent, 1=inconsistent, 2=consistent","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_clust_child", "code": "BAS_CLUST_CH",
        "name": "Consonant Cluster Reduction Baseline",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline for consonant cluster reduction across 2- and 3-element clusters.",
        "defect_id": "defect_clust_child",
        "sections": [
            _bsec("bsec_clust_ch_1","Cluster Production Probe","Assess accuracy of 2- and 3-element clusters.",1,"defect_clust_child",[
                _bitem("bitem_clust_ch_01",1,"Two-element clusters","Say: stop, play, blue, tree, flag, swim","stop play blue tree flag swim","stop play blue tree flag swim","auto_phoneme_only",scope="word"),
                _bitem("bitem_clust_ch_02",2,"Three-element clusters","Say: spring, string, splash, squeal","spring string splash squeal","spring string splash squeal","auto_phoneme_only",scope="word"),
                _bitem("bitem_clust_ch_03",3,"Cluster sentence","Read: Strong spiders spin sticky spiral strings.","Strong spiders spin sticky spiral strings.","Strong spiders spin sticky spiral strings.","auto_phoneme_only",scope="sentence"),
            ]),
            _bsec("bsec_clust_ch_2","Severity Rating","Clinician rates cluster reduction severity.",2,"defect_clust_child",[
                _bitem("bitem_clust_ch_04",1,"Cluster reduction severity","Rate severity: 0=none, 1=mild, 2=moderate, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_devstut_child", "code": "BAS_DEVSTUT_CH",
        "name": "Developmental Stuttering Baseline (SSI-4)",
        "domain": "fluency", "administration_method": "clinician_administered",
        "description": "Stuttering severity assessment using reading, monologue, and clinician-rated secondary behaviours.",
        "defect_id": "defect_devstut_child",
        "sections": [
            _bsec("bsec_devstut_ch_1","Fluency Sample — Reading and Monologue","Collect speech samples for disfluency analysis.",1,"defect_devstut_child",[
                _bitem("bitem_devstut_ch_01",1,"Reading passage","Read aloud: 'One morning the little rabbit went to the garden...' (100+ words)","The rabbit went to the garden to find some carrots. He hopped along the path. Suddenly he saw a fox. He ran as fast as he could back to his home.","(reading passage text)","auto_simple",scope="sentence",wpm_range={"min":40,"max":100}),
                _bitem("bitem_devstut_ch_02",2,"Monologue sample","Tell me what you like to do at weekends","(spontaneous speech — 200+ syllables)","(free speech)","auto_simple",scope="discourse",wpm_range={"min":40,"max":120}),
                _bitem("bitem_devstut_ch_03",3,"Percent syllables stuttered (PSS)","Clinician calculates PSS from above samples","(calculated from samples)","N/A","clinician_rated",max_score=7,scoring_method="rating_scale",response_type="clinician"),
            ]),
            _bsec("bsec_devstut_ch_2","Physical Concomitants","Rate secondary stuttering behaviours.",2,"defect_devstut_child",[
                _bitem("bitem_devstut_ch_04",1,"Distracting sounds","Rate distracting sounds (0–5 scale)","(Clinician observes)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_devstut_ch_05",2,"Physical concomitants total","Rate: facial grimaces, head movements, limb movements","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_clutter_child", "code": "BAS_CLUT_CH",
        "name": "Cluttering Baseline Assessment (Child)",
        "domain": "fluency", "administration_method": "automated",
        "description": "Baseline for cluttering — excessive rate and reduced intelligibility.",
        "defect_id": "defect_clutter_child",
        "sections": [
            _bsec("bsec_clut_ch_1","Rate and Intelligibility Sample","Collect reading and spontaneous speech samples.",1,"defect_clutter_child",[
                _bitem("bitem_clut_ch_01",1,"Paced reading sample","Read this passage at your natural rate: 'The children played in the park on a sunny day. They ran and laughed and had a great time.'","The children played in the park on a sunny day. They ran and laughed and had a great time.","The children played in the park on a sunny day. They ran and laughed and had a great time.","auto_simple",scope="sentence",wpm_range={"min":60,"max":200}),
                _bitem("bitem_clut_ch_02",2,"Spontaneous speech sample","Tell me about your favourite game","(free speech — 100+ words)","(free speech)","auto_simple",scope="discourse"),
            ]),
            _bsec("bsec_clut_ch_2","Clinician Rating","Rate cluttering features.",2,"defect_clutter_child",[
                _bitem("bitem_clut_ch_03",1,"Rate intelligibility rating","Rate overall intelligibility: 1=highly intelligible, 5=largely unintelligible","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_clut_ch_04",2,"Cluttering severity rating","Overall cluttering severity: 0=none, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_exprlang_child", "code": "BAS_EXPRLANG_CH",
        "name": "Expressive Language Baseline (Child)",
        "domain": "language", "administration_method": "automated",
        "description": "Baseline for expressive language — vocabulary, sentence structure, and narrative.",
        "defect_id": "defect_exprlang_child",
        "sections": [
            _bsec("bsec_exprlang_ch_1","Vocabulary and Sentence Production","Assess expressive vocabulary and sentence formulation.",1,"defect_exprlang_child",[
                _bitem("bitem_exprlang_ch_01",1,"Expressive vocabulary — picture naming","Name each picture (10 nouns, 5 verbs, 5 adjectives)","(picture set — 20 items)","(target vocabulary)","auto_simple",scope="word"),
                _bitem("bitem_exprlang_ch_02",2,"Sentence formulation — picture description","Describe what is happening in this picture in 2-3 sentences","(action picture)","(descriptive sentences)","auto_simple",scope="discourse",wpm_range={"min":50,"max":120}),
                _bitem("bitem_exprlang_ch_03",3,"Sentence repetition","Repeat: 'The boy is kicking the big red ball.' / 'Yesterday she went to her grandmother's house.'","The boy is kicking the big red ball. Yesterday she went to her grandmother's house.","The boy is kicking the big red ball. Yesterday she went to her grandmother's house.","auto_simple",scope="sentence"),
                _bitem("bitem_exprlang_ch_04",4,"WH-question responses","Answer: 'What do you do when you are hungry?'","(spontaneous answer)","I eat food / I get a snack / I ask for food","auto_simple",scope="discourse"),
            ]),
            _bsec("bsec_exprlang_ch_2","Narrative and Morphosyntax","Assess narrative structure and grammatical accuracy.",2,"defect_exprlang_child",[
                _bitem("bitem_exprlang_ch_05",1,"Narrative retelling — story grammar","Retell the Three Billy Goats Gruff story","(retold narrative)","(story elements: characters, setting, problem, resolution)","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_reclang_child", "code": "BAS_RECLANG_CH",
        "name": "Receptive Language Baseline (Child)",
        "domain": "language", "administration_method": "clinician_administered",
        "description": "Baseline for receptive language — instruction following, comprehension, and vocabulary.",
        "defect_id": "defect_reclang_child",
        "sections": [
            _bsec("bsec_reclang_ch_1","Instruction Following","Assess comprehension of one, two, and three-step instructions.",1,"defect_reclang_child",[
                _bitem("bitem_reclang_ch_01",1,"One-step instruction","Follow: 'Clap your hands.'","(action performed)","clapped","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_reclang_ch_02",2,"Two-step instruction","Follow: 'Touch your nose, then stand up.'","(actions performed)","touched nose, stood up","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_reclang_ch_03",3,"Three-step instruction","Follow: 'Put the pencil on the book, then close your eyes, then point to the door.'","(actions performed)","3-step sequence","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
            _bsec("bsec_reclang_ch_2","Vocabulary and Question Comprehension","Assess receptive vocabulary and question comprehension.",2,"defect_reclang_child",[
                _bitem("bitem_reclang_ch_04",1,"Point-to picture vocabulary","Point to: 'Show me the one that is used to cut paper'","(pointing response)","scissors","auto_simple",scope="word"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_latelang_child", "code": "BAS_LATELANG_CH",
        "name": "Late Language Emergence Baseline",
        "domain": "language", "administration_method": "clinician_administered",
        "description": "Baseline for late language emergence — vocabulary size, first combinations, comprehension.",
        "defect_id": "defect_latelang_child",
        "sections": [
            _bsec("bsec_latelang_ch_1","Vocabulary and Combinations","Assess vocabulary size and early word combinations.",1,"defect_latelang_child",[
                _bitem("bitem_latelang_ch_01",1,"Vocabulary elicitation","Name each picture: cup, ball, dog, car, book, shoe","cup ball dog car book shoe","cup ball dog car book shoe","auto_simple",scope="word"),
                _bitem("bitem_latelang_ch_02",2,"Two-word combination","Describe what you see: (picture of big dog)","big dog / dog running / dog eating","big dog","auto_simple",scope="word",wpm_range={"min":40,"max":80}),
            ]),
            _bsec("bsec_latelang_ch_2","Comprehension and Parent Report","Clinician rates and obtains parent report.",2,"defect_latelang_child",[
                _bitem("bitem_latelang_ch_03",1,"Vocabulary size estimate (parent report)","Clinician records parent's estimate of vocabulary size","(Parent report: number of words)","(vocabulary count)","clinician_rated",max_score=None,scoring_method="count",response_type="clinician"),
                _bitem("bitem_latelang_ch_04",2,"Language severity rating","Rate overall severity: 1=mild, 3=moderate, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_vocnod_child", "code": "BAS_VOCNOD_CH",
        "name": "Vocal Nodules Baseline (Child)",
        "domain": "voice", "administration_method": "automated",
        "description": "Baseline voice quality assessment for children with vocal nodules.",
        "defect_id": "defect_vocnod_child",
        "sections": [
            _bsec("bsec_vocnod_ch_1","Phonation Quality","Assess voice quality and phonation time.",1,"defect_vocnod_child",[
                _bitem("bitem_vocnod_ch_01",1,"Maximum phonation time","Sustain /a/ as long as possible","ahh (sustained)","(duration)","auto_simple",scope="phoneme",wpm_range={"min":0,"max":0}),
                _bitem("bitem_vocnod_ch_02",2,"Sustained /s/ versus /z/ ratio","Sustain /s/ then /z/ for maximum time","sss / zzz","(durations)","auto_simple",scope="phoneme"),
            ]),
            _bsec("bsec_vocnod_ch_2","GRBAS Voice Rating","Clinician rates voice quality using GRBAS.",2,"defect_vocnod_child",[
                _bitem("bitem_vocnod_ch_03",1,"GRBAS — Grade","Rate overall grade of dysphonia (0–3)","(Clinician rates from voice sample)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_vocnod_ch_04",2,"GRBAS — Roughness and Breathiness","Rate roughness (R) and breathiness (B) separately (0–3 each)","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_reson_child", "code": "BAS_RESON_CH",
        "name": "Resonance Disorder Baseline (Child)",
        "domain": "voice", "administration_method": "clinician_administered",
        "description": "Baseline for hypernasality — nasal emission, oral pressure consonants, and resonance rating.",
        "defect_id": "defect_reson_child",
        "sections": [
            _bsec("bsec_reson_ch_1","Oral Pressure Consonants","Assess oral pressure consonant accuracy.",1,"defect_reson_child",[
                _bitem("bitem_reson_ch_01",1,"Pressure consonant probe","Say: pa-pa-pa / ta-ta-ta / ka-ka-ka / bee-bee-bee","pa-pa-pa ta-ta-ta ka-ka-ka bee-bee-bee","pa-pa-pa ta-ta-ta ka-ka-ka bee-bee-bee","auto_phoneme_only",target_phoneme="/p/,/t/,/k/,/b/",scope="phoneme"),
                _bitem("bitem_reson_ch_02",2,"Pressure consonant words","Say: Peter, table, kite, baby","Peter table kite baby","Peter table kite baby","auto_phoneme_only",target_phoneme="/p/,/t/,/k/,/b/",scope="word"),
            ]),
            _bsec("bsec_reson_ch_2","Resonance Rating","Clinician rates nasality and nasal emission.",2,"defect_reson_child",[
                _bitem("bitem_reson_ch_03",1,"Hypernasality rating","Rate hypernasality: 0=normal, 1=mild, 2=moderate, 3=severe","(Clinician rates from sample)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_reson_ch_04",2,"Nasal emission severity","Rate nasal emission: 0=absent, 1=inconsistent, 2=consistent, 3=obligatory","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_cas_child", "code": "BAS_CAS_CH",
        "name": "Childhood Apraxia of Speech Baseline",
        "domain": "articulation", "administration_method": "clinician_administered",
        "description": "CAS baseline — inconsistency probe, DDK, and prosodic assessment.",
        "defect_id": "defect_cas_child",
        "sections": [
            _bsec("bsec_cas_ch_1","Inconsistency and Motor Planning","Probe articulatory inconsistency across repeated productions.",1,"defect_cas_child",[
                _bitem("bitem_cas_ch_01",1,"10-word inconsistency probe (3 trials)","Say each word three times: baby, table, cupboard, butterfly, elephant","baby baby baby / table table table / (3 trials × 5 words)","(consistent or inconsistent productions)","auto_phoneme_only",scope="word"),
                _bitem("bitem_cas_ch_02",2,"DDK — pa-ta-ka","Say pa-ta-ka as fast as possible for 5 seconds","pa-ta-ka pa-ta-ka pa-ta-ka","pa-ta-ka (continuous)","auto_simple",scope="phoneme",wpm_range={"min":100,"max":300}),
                _bitem("bitem_cas_ch_03",3,"Polysyllabic word production","Say: spaghetti, caterpillar, hippopotamus","spaghetti caterpillar hippopotamus","spaghetti caterpillar hippopotamus","auto_phoneme_only",scope="word"),
            ]),
            _bsec("bsec_cas_ch_2","Prosody and Clinician Rating","Assess prosodic abnormalities and rate overall severity.",2,"defect_cas_child",[
                _bitem("bitem_cas_ch_04",1,"Prosodic abnormality rating","Rate prosodic abnormality: 0=normal, 1=mild, 2=moderate, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_cas_ch_05",2,"Inconsistency score (clinician calculated)","Rate inconsistency: percentage of inconsistent productions across 3 trials","(Clinician calculates %)","N/A","clinician_rated",max_score=None,scoring_method="percentage_correct",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_asd_child", "code": "BAS_ASD_CH",
        "name": "ASD Social Communication Baseline",
        "domain": "other", "administration_method": "clinician_administered",
        "description": "Social communication profile for ASD — pragmatic language, turn-taking, and joint attention.",
        "defect_id": "defect_asd_child",
        "sections": [
            _bsec("bsec_asd_ch_1","Pragmatic Language Probe","Assess conversational pragmatics.",1,"defect_asd_child",[
                _bitem("bitem_asd_ch_01",1,"Greeting initiation","Clinician enters — does patient initiate greeting?","(Observation)","greeting produced","auto_simple",scope="word"),
                _bitem("bitem_asd_ch_02",2,"Topic maintenance","Engage in 5-minute conversation on preferred topic","(5-minute conversation sample)","(on-topic contributions)","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_asd_ch_03",3,"Turn-taking appropriateness","Rate turn-taking: 0=no turns, 3=sometimes, 5=appropriate","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
            _bsec("bsec_asd_ch_2","Perspective-Taking and Flexibility","Assess theory of mind and topic flexibility.",2,"defect_asd_child",[
                _bitem("bitem_asd_ch_04",1,"Emotion recognition","Point to: happy / sad / angry / surprised / scared","(pointing response)","(emotion label)","clinician_rated",max_score=5,scoring_method="count",response_type="clinician"),
                _bitem("bitem_asd_ch_05",2,"Social communication severity","Overall social communication severity: 1=mild, 5=severe","(Clinician rates overall)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_mute_child", "code": "BAS_MUTE_CH",
        "name": "Selective Mutism Baseline",
        "domain": "other", "administration_method": "clinician_administered",
        "description": "Baseline for selective mutism — speaking situation hierarchy and anxiety rating.",
        "defect_id": "defect_mute_child",
        "sections": [
            _bsec("bsec_mute_ch_1","Speaking Situations Hierarchy","Map speaking and non-speaking situations.",1,"defect_mute_child",[
                _bitem("bitem_mute_ch_01",1,"Speaking at home (family)","Clinician or parent rates speaking at home","Does patient speak freely at home?","yes/no + details","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_mute_ch_02",2,"Speaking with familiar adults","Rate speaking with familiar adults (teacher, doctor)","(Clinician/parent report)","(frequency rating)","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
            _bsec("bsec_mute_ch_2","Anxiety and Elicited Speech","Rate anxiety and attempt elicited vocalisation.",2,"defect_mute_child",[
                _bitem("bitem_mute_ch_03",1,"Anxiety in clinical setting rating","Rate observed anxiety: 0=relaxed, 5=highly anxious","(Clinician observes)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_mute_ch_04",2,"Elicited vocalisation attempt","Can the patient produce any sound in the clinical setting?","(Any vocalisation — whisper, hum, word)","(any vocalisation)","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    # ── ADULT BASELINES ───────────────────────────────────────────────────────

    {
        "baseline_id": "ba_dysart_adult", "code": "BAS_DYSART_AD",
        "name": "Acquired Dysarthria Baseline",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline for acquired dysarthria — intelligibility, DDK, and severity rating.",
        "defect_id": "defect_dysart_adult",
        "sections": [
            _bsec("bsec_dysart_ad_1","Intelligibility and Motor Speech","Measure intelligibility in single words and sentences.",1,"defect_dysart_adult",[
                _bitem("bitem_dysart_ad_01",1,"Single word intelligibility","Say each word: cat, door, bed, flag, spring, elephant","cat door bed flag spring elephant","cat door bed flag spring elephant","auto_simple",scope="word"),
                _bitem("bitem_dysart_ad_02",2,"Sentence intelligibility","Read: 'The boy kicked the ball across the field.'","The boy kicked the ball across the field.","The boy kicked the ball across the field.","auto_simple",scope="sentence"),
                _bitem("bitem_dysart_ad_03",3,"DDK rate","Say pa-ta-ka for 5 seconds — as fast and clear as possible","pa-ta-ka (repeated)","pa-ta-ka","auto_simple",scope="phoneme",wpm_range={"min":60,"max":300}),
            ]),
            _bsec("bsec_dysart_ad_2","Severity Rating","Frenchay/clinical rating.",2,"defect_dysart_adult",[
                _bitem("bitem_dysart_ad_04",1,"Dysarthria severity rating","Overall intelligibility rating: 1=normal, 5=unintelligible","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_dysart_ad_05",2,"Subsystem involved (respiration, phonation, resonance, articulation, prosody)","Rate each subsystem 0–3","(Clinician rates each subsystem)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_lisp_adult", "code": "BAS_LISP_AD",
        "name": "Sibilant Lisp Baseline Assessment (Adult)",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline for persisting or acquired adult sibilant distortion.",
        "defect_id": "defect_lisp_adult",
        "sections": [
            _bsec("bsec_lisp_ad_1","Sibilant Accuracy","Assess /s/ and /z/ across all positions.",1,"defect_lisp_adult",[
                _bitem("bitem_lisp_ad_01",1,"/s/ isolation","Hold /s/ for 5 seconds","ssssss","ssss","auto_phoneme_only",target_phoneme="/s/",scope="phoneme"),
                _bitem("bitem_lisp_ad_02",2,"Sibilant word probe","Say: success, session, scissors, business, phrases","success session scissors business phrases","(5 targets)","auto_phoneme_only",target_phoneme="/s/,/z/",scope="word"),
                _bitem("bitem_lisp_ad_03",3,"Sibilant sentence","Read: 'Susan successfully organised six essential sessions.'","Susan successfully organised six essential sessions.","Susan successfully organised six essential sessions.","auto_phoneme_only",target_phoneme="/s/",scope="sentence"),
            ]),
            _bsec("bsec_lisp_ad_2","Lisp Classification","Clinician classifies lisp type.",2,"defect_lisp_adult",[
                _bitem("bitem_lisp_ad_04",1,"Lisp type classification","Classify: interdental / lateral / palatal","(Clinician classifies)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_rhot_adult", "code": "BAS_RHOT_AD",
        "name": "Rhotacism Baseline (Adult)",
        "domain": "articulation", "administration_method": "automated",
        "description": "Baseline for post-neurological /r/ distortion in adults.",
        "defect_id": "defect_rhot_adult",
        "sections": [
            _bsec("bsec_rhot_ad_1","/r/ Production Probe","Assess /r/ accuracy across positions.",1,"defect_rhot_adult",[
                _bitem("bitem_rhot_ad_01",1,"/r/ isolation and syllables","Produce: r / ra / ri / re / ro / ar / or","r ra ri re ro ar or","r ra ri re ro ar or","auto_phoneme_only",target_phoneme="/r/",scope="phoneme"),
                _bitem("bitem_rhot_ad_02",2,"/r/ word probe","Say: rapid, river, report, quarter, mirror, career","rapid river report quarter mirror career","(6 targets)","auto_phoneme_only",target_phoneme="/r/",scope="word"),
                _bitem("bitem_rhot_ad_03",3,"/r/ sentence","Read: 'The river runs rapidly around the rocky ridge.'","The river runs rapidly around the rocky ridge.","The river runs rapidly around the rocky ridge.","auto_phoneme_only",target_phoneme="/r/",scope="sentence"),
            ]),
            _bsec("bsec_rhot_ad_2","Neurological Context","Clinician rates and documents neurological context.",2,"defect_rhot_adult",[
                _bitem("bitem_rhot_ad_04",1,"Neurological context rating","Rate motor severity affecting /r/: 1=mild, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_neurstut_adult", "code": "BAS_NEURSTUT_AD",
        "name": "Neurogenic Stuttering Baseline",
        "domain": "fluency", "administration_method": "clinician_administered",
        "description": "Baseline for acquired neurogenic stuttering — fluency sample and severity rating.",
        "defect_id": "defect_neurstut_adult",
        "sections": [
            _bsec("bsec_neurstut_ad_1","Fluency Sample","Collect reading and conversational samples.",1,"defect_neurstut_adult",[
                _bitem("bitem_neurstut_ad_01",1,"Reading sample","Read aloud for 2 minutes","(reading passage — 200+ words)","(passage)","auto_simple",scope="sentence",wpm_range={"min":40,"max":150}),
                _bitem("bitem_neurstut_ad_02",2,"Monologue","Tell me about your daily routine","(spontaneous speech — 200+ syllables)","(free speech)","auto_simple",scope="discourse"),
                _bitem("bitem_neurstut_ad_03",3,"PSS calculation","Clinician calculates percent syllables stuttered","(calculated)","N/A","clinician_rated",max_score=7,scoring_method="rating_scale",response_type="clinician"),
            ]),
            _bsec("bsec_neurstut_ad_2","Neurogenic Profile","Distinguish neurogenic from developmental profile.",2,"defect_neurstut_adult",[
                _bitem("bitem_neurstut_ad_04",1,"Adaptation effect","Does stuttering reduce across 5 readings of same passage?","(Clinician tests adaptation)","(yes/no/partial)","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_neurstut_ad_05",2,"Neurogenic features rating","Rate neurogenic indicators: equal stuttering in reading and monologue, no adaptation, no anxiety","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_clutter_adult", "code": "BAS_CLUT_AD",
        "name": "Cluttering Baseline (Adult)",
        "domain": "fluency", "administration_method": "automated",
        "description": "Adult cluttering baseline — rate, intelligibility, and self-awareness.",
        "defect_id": "defect_clutter_adult",
        "sections": [
            _bsec("bsec_clut_ad_1","Rate and Intelligibility","Sample natural rate and measure intelligibility.",1,"defect_clutter_adult",[
                _bitem("bitem_clut_ad_01",1,"Spontaneous speech sample","Tell me about your work or a recent project","(free speech — 200+ words)","(free speech)","auto_simple",scope="discourse",wpm_range={"min":60,"max":300}),
                _bitem("bitem_clut_ad_02",2,"Paced reading","Read at natural rate: (passage 150 words)","(reading passage)","(passage)","auto_simple",scope="sentence",wpm_range={"min":80,"max":300}),
            ]),
            _bsec("bsec_clut_ad_2","Self-Monitoring and Severity","Rate self-awareness and overall severity.",2,"defect_clutter_adult",[
                _bitem("bitem_clut_ad_03",1,"Self-monitoring rating","Rate self-awareness of cluttering: 0=unaware, 5=highly aware","(Clinician rates via interview)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_clut_ad_04",2,"Overall cluttering severity","Rate severity: 1=mild, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_psychdis_adult", "code": "BAS_PSYDIS_AD",
        "name": "Psychogenic Disfluency Baseline",
        "domain": "fluency", "administration_method": "clinician_administered",
        "description": "Baseline for psychogenic disfluency — fluency sample, anxiety probe, and consistency.",
        "defect_id": "defect_psychdis_adult",
        "sections": [
            _bsec("bsec_psychdis_ad_1","Fluency and Consistency","Sample fluency across contexts.",1,"defect_psychdis_adult",[
                _bitem("bitem_psychdis_ad_01",1,"Reading sample","Read this passage aloud","(150-word passage)","(passage)","auto_simple",scope="sentence"),
                _bitem("bitem_psychdis_ad_02",2,"Conversational sample","Tell me about your life recently","(free speech)","(free speech)","auto_simple",scope="discourse"),
                _bitem("bitem_psychdis_ad_03",3,"Distraction condition","Count backwards from 100 by 3s","97, 94, 91, 88...","(counting sequence)","auto_simple",scope="word"),
            ]),
            _bsec("bsec_psychdis_ad_2","Psychological and Consistency Indicators","Clinician rates psychogenic features.",2,"defect_psychdis_adult",[
                _bitem("bitem_psychdis_ad_04",1,"Variability across conditions","Rate variability of disfluency across tasks: 0=consistent, 5=highly variable","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_psychdis_ad_05",2,"Psychological profile indicator","Document onset, psychological context, and severity","(Interview documentation)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_aphexpr_adult", "code": "BAS_APHEXPR_AD",
        "name": "Expressive Aphasia Baseline (Broca's)",
        "domain": "language", "administration_method": "clinician_administered",
        "description": "Baseline for Broca's aphasia — naming, repetition, and spontaneous speech.",
        "defect_id": "defect_aphexpr_adult",
        "sections": [
            _bsec("bsec_aphexpr_ad_1","Naming and Repetition","Confrontation naming and sentence repetition.",1,"defect_aphexpr_adult",[
                _bitem("bitem_aphexpr_ad_01",1,"Confrontation naming (10 items)","Name each picture: pencil, envelope, volcano, hammock, dominoes","pencil envelope volcano hammock dominoes","(10 targets)","auto_simple",scope="word"),
                _bitem("bitem_aphexpr_ad_02",2,"Sentence repetition","Repeat: 'The woman is buying flowers at the market.'","The woman is buying flowers at the market.","The woman is buying flowers at the market.","auto_simple",scope="sentence"),
                _bitem("bitem_aphexpr_ad_03",3,"Verbal fluency — animals","Name as many animals as you can in 60 seconds","(spontaneous list)","(animal names)","auto_simple",scope="word",wpm_range={"min":20,"max":80}),
            ]),
            _bsec("bsec_aphexpr_ad_2","Connected Speech","Assess spontaneous speech output and grammar.",2,"defect_aphexpr_adult",[
                _bitem("bitem_aphexpr_ad_04",1,"Cookie Theft picture description","Describe the Cookie Theft picture","(picture description)","(target content units)","auto_simple",scope="discourse"),
                _bitem("bitem_aphexpr_ad_05",2,"Aphasia severity rating","Rate expressive severity: 1=severe, 5=mild","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_aphrec_adult", "code": "BAS_APHREC_AD",
        "name": "Receptive Aphasia Baseline (Wernicke's)",
        "domain": "language", "administration_method": "clinician_administered",
        "description": "Baseline for Wernicke's aphasia — comprehension, pointing, and yes/no responses.",
        "defect_id": "defect_aphrec_adult",
        "sections": [
            _bsec("bsec_aphrec_ad_1","Auditory Comprehension","Assess yes/no, word, and sentence comprehension.",1,"defect_aphrec_adult",[
                _bitem("bitem_aphrec_ad_01",1,"Yes/No questions","Answer: Is your name John? Is it raining inside?","yes / no responses","yes / no","clinician_rated",max_score=5,scoring_method="count",response_type="clinician"),
                _bitem("bitem_aphrec_ad_02",2,"Point-to vocabulary","Point to: the animal that barks / something you write with","(pointing response)","dog / pen","clinician_rated",max_score=5,scoring_method="count",response_type="clinician"),
                _bitem("bitem_aphrec_ad_03",3,"Follow instructions","Follow: Touch your nose with your right hand","(action)","touched nose with right hand","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
            _bsec("bsec_aphrec_ad_2","Paraphasia and Connected Speech","Assess paraphasias and jargon.",2,"defect_aphrec_adult",[
                _bitem("bitem_aphrec_ad_04",1,"Spontaneous speech paraphasia rating","Rate paraphasia frequency: 0=none, 3=frequent, 5=predominantly jargon","(Clinician rates from speech sample)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_aphrec_ad_05",2,"Comprehension severity rating","Rate comprehension deficit severity: 1=mild, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_anomia_adult", "code": "BAS_ANOMIA_AD",
        "name": "Anomia Baseline Assessment",
        "domain": "language", "administration_method": "automated",
        "description": "Baseline for anomia — confrontation naming, verbal fluency, and word retrieval strategies.",
        "defect_id": "defect_anomia_adult",
        "sections": [
            _bsec("bsec_anomia_ad_1","Naming and Fluency","Confrontation naming and category fluency.",1,"defect_anomia_adult",[
                _bitem("bitem_anomia_ad_01",1,"Confrontation naming (15 items)","Name each picture: butterfly, stethoscope, compass, umbrella, envelope, scissors, volcano, lighthouse, hammock, anchor, dominoes, thermometer, syringe, wrench, binoculars","(15 targets)","(15 target words)","auto_simple",scope="word"),
                _bitem("bitem_anomia_ad_02",2,"Category fluency — animals","Name as many animals as possible in 60 seconds","(spontaneous)","(animal list)","auto_simple",scope="word",wpm_range={"min":10,"max":60}),
                _bitem("bitem_anomia_ad_03",3,"Letter fluency — F words","Name as many words starting with F as possible in 60 seconds","(spontaneous)","(F-word list)","auto_simple",scope="word"),
            ]),
            _bsec("bsec_anomia_ad_2","Word Retrieval Strategies and Severity","Assess strategy use and rate severity.",2,"defect_anomia_adult",[
                _bitem("bitem_anomia_ad_04",1,"Circumlocution rating","Rate circumlocution frequency: 0=absent, 3=frequent","(Clinician rates from naming probe)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_anomia_ad_05",2,"Anomia severity","Rate anomia severity: 1=mild, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_vocnod_adult", "code": "BAS_VOCNOD_AD",
        "name": "Vocal Nodules Baseline (Adult)",
        "domain": "voice", "administration_method": "automated",
        "description": "Voice quality baseline for adult vocal nodules — MPT, s/z ratio, GRBAS.",
        "defect_id": "defect_vocnod_adult",
        "sections": [
            _bsec("bsec_vocnod_ad_1","Acoustic and Phonatory Measures","Baseline acoustic voice measures.",1,"defect_vocnod_adult",[
                _bitem("bitem_vocnod_ad_01",1,"Maximum phonation time — /a/","Sustain /a/ for as long as possible after a full breath","ahh (sustained)","(duration)","auto_simple",scope="phoneme",wpm_range={"min":0,"max":0}),
                _bitem("bitem_vocnod_ad_02",2,"Maximum phonation time — /s/ and /z/","Sustain /s/ then /z/ for maximum time (s/z ratio)","sss / zzz","(durations)","auto_simple",scope="phoneme"),
                _bitem("bitem_vocnod_ad_03",3,"Connected speech voice quality","Read: 'Rainbow passage — first paragraph'","When the sunlight strikes raindrops in the air, they act as a prism and form a rainbow.","When the sunlight strikes raindrops in the air, they act as a prism and form a rainbow.","auto_simple",scope="sentence"),
            ]),
            _bsec("bsec_vocnod_ad_2","Voice Quality Rating","GRBAS rating from samples.",2,"defect_vocnod_adult",[
                _bitem("bitem_vocnod_ad_04",1,"GRBAS — Grade","Rate G (overall grade): 0=normal, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_vocnod_ad_05",2,"GRBAS — R, B, A, S","Rate R(roughness), B(breathiness), A(asthenia), S(strain) each 0–3","(Clinician rates each)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_vcpar_adult", "code": "BAS_VCPAR_AD",
        "name": "Vocal Cord Paralysis Baseline",
        "domain": "voice", "administration_method": "clinician_administered",
        "description": "Baseline for vocal fold paralysis — phonation quality, loudness, and effort.",
        "defect_id": "defect_vcpar_adult",
        "sections": [
            _bsec("bsec_vcpar_ad_1","Phonatory Function","Assess phonation onset and sustain.",1,"defect_vcpar_adult",[
                _bitem("bitem_vcpar_ad_01",1,"MPT — sustained /a/","Sustain /a/ as long as possible","ahh","(duration)","auto_simple",scope="phoneme"),
                _bitem("bitem_vcpar_ad_02",2,"Hard versus soft voice onset","Produce hard onset 'up' then easy onset 'up'","up (hard) / up (easy)","up","auto_simple",scope="word"),
                _bitem("bitem_vcpar_ad_03",3,"Loudness during connected speech","Read at maximum comfortable loudness: 'Good morning, my name is ___.'","Good morning, my name is ___. I am pleased to meet you.","Good morning, my name is ___. I am pleased to meet you.","auto_simple",scope="sentence"),
            ]),
            _bsec("bsec_vcpar_ad_2","Clinical Rating and Effort","Rate phonatory effort and quality.",2,"defect_vcpar_adult",[
                _bitem("bitem_vcpar_ad_04",1,"Vocal effort rating","Rate phonatory effort: 1=effortless, 5=severely effortful","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_vcpar_ad_05",2,"Diplophonia and voice quality","Rate diplophonia presence: 0=absent, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_spasdys_adult", "code": "BAS_SPASDYS_AD",
        "name": "Spasmodic Dysphonia Baseline",
        "domain": "voice", "administration_method": "clinician_administered",
        "description": "Baseline for spasmodic dysphonia — voice breaks, strain, and connected speech rating.",
        "defect_id": "defect_spasdys_adult",
        "sections": [
            _bsec("bsec_spasdys_ad_1","Voice Breaks and Connected Speech","Assess voice breaks in running speech.",1,"defect_spasdys_adult",[
                _bitem("bitem_spasdys_ad_01",1,"Voice break count — reading","Count voice breaks while reading passage","When the sunlight strikes raindrops in the air, they act as a prism and form a rainbow.","(break count)","auto_simple",scope="sentence"),
                _bitem("bitem_spasdys_ad_02",2,"Vowel prolongation","Sustain /a-a-a-a/ with minimal strain","a a a a (repeated)","a a a a","auto_simple",scope="phoneme"),
            ]),
            _bsec("bsec_spasdys_ad_2","Severity and Type Rating","Clinician rates type and severity.",2,"defect_spasdys_adult",[
                _bitem("bitem_spasdys_ad_03",1,"SD type classification","Classify: adductor / abductor / mixed","(Clinician rates from voice sample)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_spasdys_ad_04",2,"Overall SD severity","Rate severity: 1=mild, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_spasdys_ad_05",3,"VHI-10 proxy (patient self-report)","Patient rates: How often does your voice problem affect your life? (1–5)","(Patient rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_aos_adult", "code": "BAS_AOS_AD",
        "name": "Acquired Apraxia of Speech Baseline",
        "domain": "articulation", "administration_method": "clinician_administered",
        "description": "Baseline for AOS — inconsistency probe, DDK, and DIVA/Mayo rating.",
        "defect_id": "defect_aos_adult",
        "sections": [
            _bsec("bsec_aos_ad_1","Inconsistency and Motor Planning","Probe articulatory inconsistency.",1,"defect_aos_adult",[
                _bitem("bitem_aos_ad_01",1,"Inconsistency probe (3 trials × 10 words)","Repeat each 3 times: tennis, artillery, impossibility","tennis (×3), artillery (×3), impossibility (×3)","(consistent vs inconsistent)","auto_phoneme_only",scope="word"),
                _bitem("bitem_aos_ad_02",2,"DDK — pa-ta-ka","Say pa-ta-ka as clearly as possible for 5 seconds","pa-ta-ka pa-ta-ka pa-ta-ka","pa-ta-ka","auto_simple",scope="phoneme",wpm_range={"min":60,"max":300}),
                _bitem("bitem_aos_ad_03",3,"Polysyllabic words","Say: catastrophe, artillery, impossibility","catastrophe artillery impossibility","catastrophe artillery impossibility","auto_phoneme_only",scope="word"),
            ]),
            _bsec("bsec_aos_ad_2","Prosody and Severity","Assess prosodic abnormality and overall severity.",2,"defect_aos_adult",[
                _bitem("bitem_aos_ad_04",1,"Prosodic abnormality severity","Rate: 0=normal, 1=mild, 2=moderate, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_aos_ad_05",2,"AOS severity rating","Overall AOS severity: 1=mild, 5=severe","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_hypodys_adult", "code": "BAS_HYPODYS_AD",
        "name": "Hypokinetic Dysarthria Baseline (Parkinson's)",
        "domain": "articulation", "administration_method": "clinician_administered",
        "description": "LSVT-aligned baseline for Parkinson's dysarthria — loudness, rate, and intelligibility.",
        "defect_id": "defect_hypodys_adult",
        "sections": [
            _bsec("bsec_hypodys_ad_1","Loudness and Rate Measures","Baseline loudness and speech rate.",1,"defect_hypodys_adult",[
                _bitem("bitem_hypodys_ad_01",1,"Maximum sustained loudness","Say 'ah' at your loudest possible volume","ahh (loud)","(loudness level)","auto_simple",scope="phoneme"),
                _bitem("bitem_hypodys_ad_02",2,"MPT — sustained /a/","Sustain /a/ for as long as possible","ahh","(duration)","auto_simple",scope="phoneme"),
                _bitem("bitem_hypodys_ad_03",3,"Conversational speech sample","Tell me what you did yesterday","(free speech — 100+ words)","(free speech)","auto_simple",scope="discourse",wpm_range={"min":40,"max":180}),
            ]),
            _bsec("bsec_hypodys_ad_2","Intelligibility and Clinical Rating","Rate intelligibility and Parkinson's dysarthria severity.",2,"defect_hypodys_adult",[
                _bitem("bitem_hypodys_ad_04",1,"Sentence intelligibility","Read: 'The annual conference will be held in the city centre next month.'","The annual conference will be held in the city centre next month.","The annual conference will be held in the city centre next month.","auto_simple",scope="sentence"),
                _bitem("bitem_hypodys_ad_05",2,"Intelligibility rating","Rate conversational intelligibility: 1=fully intelligible, 5=unintelligible","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_hypodys_ad_06",3,"Hypophonia severity","Rate monopitch and monoloudness: 0=normal, 3=severe","(Clinician rates)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

    {
        "baseline_id": "ba_spastdys_adult", "code": "BAS_SPASTDYS_AD",
        "name": "Spastic Dysarthria Baseline (Post-Stroke)",
        "domain": "articulation", "administration_method": "clinician_administered",
        "description": "Baseline for post-stroke spastic dysarthria — rate, intelligibility, and subsystem rating.",
        "defect_id": "defect_spastdys_adult",
        "sections": [
            _bsec("bsec_spastdys_ad_1","Intelligibility and Rate","Assess intelligibility and speech rate.",1,"defect_spastdys_adult",[
                _bitem("bitem_spastdys_ad_01",1,"Word intelligibility","Say: catastrophe, electricity, manipulation, rehabilitation","catastrophe electricity manipulation rehabilitation","(4 targets)","auto_simple",scope="word"),
                _bitem("bitem_spastdys_ad_02",2,"Sentence reading","Read at your natural pace: 'The old farmer walked slowly across the muddy field.'","The old farmer walked slowly across the muddy field.","The old farmer walked slowly across the muddy field.","auto_simple",scope="sentence",wpm_range={"min":40,"max":130}),
                _bitem("bitem_spastdys_ad_03",3,"DDK slow sequence","Say pa-ta-ka slowly and clearly 5 times","pa-ta-ka pa-ta-ka pa-ta-ka pa-ta-ka pa-ta-ka","pa-ta-ka","auto_simple",scope="phoneme"),
            ]),
            _bsec("bsec_spastdys_ad_2","Subsystem Rating","Frenchay Dysarthria Assessment — key subsystems.",2,"defect_spastdys_adult",[
                _bitem("bitem_spastdys_ad_04",1,"Harshness and strain rating","Rate voice harshness/strain: 0=normal, 3=severe","(Clinician rates from voice sample)","N/A","clinician_rated",max_score=3,scoring_method="rating_scale",response_type="clinician"),
                _bitem("bitem_spastdys_ad_05",2,"Overall intelligibility rating","Rate overall intelligibility: 1=normal, 5=unintelligible","(Clinician rates)","N/A","clinician_rated",max_score=5,scoring_method="rating_scale",response_type="clinician"),
            ]),
        ],
    },

]

assert len(BASELINES) == 30, f"Expected 30 baselines, got {len(BASELINES)}"


# ─── SEEDING FUNCTIONS ────────────────────────────────────────────────────────

def seed_defects(conn):
    for d in DEFECTS:
        conn.execute(text("""
            INSERT INTO defect (defect_id, code, name, category, age_group, description)
            VALUES (:defect_id, :code, :name, :category, :age_group, :description)
            ON CONFLICT (defect_id) DO NOTHING
        """), d)
    conn.commit()
    print(f"  Seeded {len(DEFECTS)} defects")


def seed_emotion_weights(conn):
    for e in EMOTION_WEIGHTS:
        conn.execute(text("""
            INSERT INTO emotion_weights_config
            (config_id, age_group, w_happy, w_excited, w_neutral, w_surprised,
             w_sad, w_angry, w_fearful, w_positive_affect, w_focused, version, created_at)
            VALUES (:config_id, :age_group, :w_happy, :w_excited, :w_neutral, :w_surprised,
                    :w_sad, :w_angry, :w_fearful, :w_positive_affect, :w_focused, :version, NOW())
            ON CONFLICT (config_id) DO NOTHING
        """), e)
    conn.commit()
    print(f"  Seeded {len(EMOTION_WEIGHTS)} emotion weight configs")


def seed_pa_thresholds(conn):
    for p in PA_THRESHOLDS:
        conn.execute(text("""
            INSERT INTO defect_pa_threshold
            (threshold_id, defect_id, min_pa_to_pass, target_phonemes,
             phoneme_scope, severity_modifier, notes, created_at)
            VALUES (:threshold_id, :defect_id, :min_pa_to_pass, :target_phonemes,
                    :phoneme_scope, :severity_modifier, :notes, NOW())
            ON CONFLICT (threshold_id) DO NOTHING
        """), p)
    conn.commit()
    print(f"  Seeded {len(PA_THRESHOLDS)} PA thresholds")


def seed_tasks(conn):
    total_tasks = 0
    total_levels = 0
    total_prompts = 0
    total_mappings = 0

    for task in TASKS:
        wpm = WPM_CONFIG[task["wpm_category"]]
        conn.execute(text("""
            INSERT INTO task (task_id, name, type, task_mode, description,
                              ideal_wpm_min, ideal_wpm_max, wpm_tolerance, created_at)
            VALUES (:task_id, :name, :type, :task_mode, :description,
                    :ideal_wpm_min, :ideal_wpm_max, :wpm_tolerance, NOW())
            ON CONFLICT (task_id) DO NOTHING
        """), {**task, **wpm})
        total_tasks += 1

        sw = SCORING_WEIGHTS[task["weight_category"]]
        conn.execute(text("""
            INSERT INTO task_scoring_weights
            (weight_id, task_id,
             speech_w_pa, speech_w_wa, speech_w_fs, speech_w_srs, speech_w_cs,
             fusion_w_speech, fusion_w_engagement,
             engagement_w_emotion, engagement_w_behavioral,
             behavioral_w_rl, behavioral_w_tc, behavioral_w_aq,
             adaptive_advance_threshold, adaptive_stay_min, adaptive_stay_max,
             adaptive_drop_threshold, adaptive_consecutive_fail_limit,
             rule_severe_pa_threshold, rule_severe_pa_score_cap,
             rule_low_eng_threshold, rule_low_eng_penalty,
             rule_high_eng_threshold, rule_high_eng_boost,
             version, notes, created_at)
            VALUES (:weight_id, :task_id,
                    :pa, :wa, :fs, :srs, :cs,
                    0.90, 0.10,
                    0.65, 0.35,
                    0.40, 0.35, 0.25,
                    75.0, 60.0, 74.0,
                    60.0, 3,
                    35.0, 45.0,
                    35.0, 5.0,
                    85.0, 5.0,
                    1, :notes, NOW())
            ON CONFLICT (weight_id) DO NOTHING
        """), {"weight_id": f"sw_{task['task_id']}", "task_id": task["task_id"],
               "pa": sw["pa"], "wa": sw["wa"], "fs": sw["fs"],
               "srs": sw["srs"], "cs": sw["cs"],
               "notes": task.get("scoring_notes")})

        for level in task["levels"]:
            conn.execute(text("""
                INSERT INTO task_level (level_id, task_id, level_name, difficulty_score)
                VALUES (:level_id, :task_id, :level_name, :difficulty_score)
                ON CONFLICT (level_id) DO NOTHING
            """), {"level_id": level["level_id"], "task_id": task["task_id"],
                   "level_name": level["level_name"],
                   "difficulty_score": level["difficulty_score"]})
            total_levels += 1

            for prompt in level["prompts"]:
                conn.execute(text("""
                    INSERT INTO prompt
                    (prompt_id, level_id, prompt_type, task_mode,
                     instruction, display_content, target_response, eval_scope,
                     speech_target, target_phonemes,
                     pass_message, partial_message, fail_message,
                     active, aq_relevance_threshold,
                     tc_mode, target_word_count, target_duration_sec, min_length_words)
                    VALUES
                    (:prompt_id, :level_id, 'exercise', :task_mode,
                     :instruction, :display_content, :target_response, :eval_scope,
                     CAST(:speech_target AS jsonb), CAST(:target_phonemes AS jsonb),
                     :pass_message, :partial_message, :fail_message,
                     TRUE, 0.60,
                     :tc_mode, :target_word_count, :target_duration_sec, :min_length_words)
                    ON CONFLICT (prompt_id) DO NOTHING
                """), {**prompt, "level_id": level["level_id"],
                       "task_mode": task["task_mode"]})
                total_prompts += 1

        for mapping in task["defect_mappings"]:
            conn.execute(text("""
                INSERT INTO task_defect_mapping
                (mapping_id, task_id, defect_id, relevance_level)
                VALUES (:mapping_id, :task_id, :defect_id, :relevance_level)
                ON CONFLICT (task_id, defect_id) DO NOTHING
            """), {"mapping_id": f"tdm_{task['task_id']}_{mapping['defect_id']}",
                   "task_id": task["task_id"],
                   "defect_id": mapping["defect_id"],
                   "relevance_level": mapping["relevance_level"]})
            total_mappings += 1

    conn.commit()
    print(f"  Seeded {total_tasks} tasks | {total_levels} levels | "
          f"{total_prompts} prompts | {total_mappings} defect mappings")


def seed_baselines(conn):
    for b in BASELINES:
        conn.execute(text("""
            INSERT INTO baseline_assessment
            (baseline_id, code, name, domain, description, administration_method, created_at)
            VALUES (:baseline_id, :code, :name, :domain, :description, :administration_method, NOW())
            ON CONFLICT (baseline_id) DO NOTHING
        """), b)

        conn.execute(text("""
            INSERT INTO baseline_defect_mapping
            (mapping_id, baseline_id, defect_id, relevance_level)
            VALUES (:mapping_id, :baseline_id, :defect_id, 'primary')
            ON CONFLICT (baseline_id, defect_id) DO NOTHING
        """), {"mapping_id": f"bdm_{b['defect_id']}",
               "baseline_id": b["baseline_id"],
               "defect_id": b["defect_id"]})

        for sec in b["sections"]:
            conn.execute(text("""
                INSERT INTO baseline_section
                (section_id, baseline_id, section_name, instructions, order_index, target_defect_id)
                VALUES (:section_id, :baseline_id, :section_name, :instructions,
                        :order_index, :target_defect_id)
                ON CONFLICT (section_id) DO NOTHING
            """), {**sec, "baseline_id": b["baseline_id"]})

            for item in sec["items"]:
                conn.execute(text("""
                    INSERT INTO baseline_item
                    (item_id, section_id, order_index, task_name, instruction,
                     display_content, expected_output, response_type, target_phoneme,
                     formula_mode, formula_weights, wpm_range, defect_codes,
                     max_score, scoring_method, scope)
                    VALUES
                    (:item_id, :section_id, :order_index, :task_name, :instruction,
                     :display_content, :expected_output, :response_type, :target_phoneme,
                     :formula_mode, CAST(:formula_weights AS jsonb), CAST(:wpm_range AS jsonb), CAST(:defect_codes AS jsonb),
                     :max_score, :scoring_method, :scope)
                    ON CONFLICT (item_id) DO NOTHING
                """), {**item, "section_id": sec["section_id"]})

    conn.commit()
    print(f"  Seeded {len(BASELINES)} baseline assessments with sections and items")


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def seed_all():
    engine = sa.create_engine(settings.database_url_sync, echo=False)
    with engine.connect() as conn:
        print("Seeding defects...")
        seed_defects(conn)
        print("Seeding emotion weights...")
        seed_emotion_weights(conn)
        print("Seeding PA thresholds...")
        seed_pa_thresholds(conn)
        print("Seeding tasks (levels, prompts, weights, mappings)...")
        seed_tasks(conn)
        print("Seeding baselines (sections, items, defect mappings)...")
        seed_baselines(conn)
    engine.dispose()
    print("\nSeed complete.")


if __name__ == "__main__":
    seed_all()
