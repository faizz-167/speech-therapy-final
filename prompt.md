Adaptive engine flow:
Each daily session contains 2 tasks, and each task initially has 3 exercises. The system evaluates each attempt using speech score and engagement score, producing a decision: advance, stay, or drop.

If the user passes an exercise, move to the next exercise.
If the user fails, allow up to 3 retries.
If the user still fails:
If the current level is above Beginner, degrade the level and add a replacement exercise.

current problem: each task contains 3 exercises. If user fails 3 attempt the adaptive engine works and the exercise degrade for specific task that user fails but iF it has another exercise it remains unchanged. 
eg:
a task contains 3 exercises
    1- intermidiate
    2- intermidiate
    3- intermidiate
user passed in first exercise which is in intermidiate level and goes to second exercise which is also intermidiate but user fail the 3 attempt now the adaptive engine works and give the degraded exercise for that specific exercise which was in beginer level but the third exercise which was in intermidiate level remains unchanged.

solution: If the user fails any exercise in 3 attempts the adaptive engine should degrade the exercise the current attended exercise and remaining unattented exercise 

extras: 
1. the therapist get notified when user fails 3 attempts in any task
2. The adaptive engine should work 2 times per tasks. For eg: if user fails in first exercise and adaptive engine works and give the degraded exercise but user again fails in that exercise the adaptive engine should work again and give the degraded exercise again. but it should not work more than 2 times per tasks.
3. If the user fails again after the adaptive engine works 2 times we notify the therapist that the user is not able to perform the task with task name and score of exercise which the patient fails and the adaptive enginer should change the weekly plan(regenerate) accroding to the patient's performance level and once it regenerates, the plan should be given for the therapist approval. the adpative engine shouls not reflect the regenerated plan to the patient without the approval of therapist
4. beginner should never degrade further.system must choose a different prompt at beginner level preferably one not already attempted in this task session
5. After 2 failed adaptive interventions, the task should probably end in a state such as "escalated for therapist review" rather than waiting for a pass.
6. Initially, when the task plan is getting generated for the first time by the therapist, it should have the same level range for all the exercise in the task exercise. There shouldn't be any mixed session range for seach exercise to carry its own level independently. Once the patient attempts the task and we store the results in the database. For the next week, when the same task arrives we'll check the scores in the database and also the inital level the therapist choose to start with the exercise. Based on this, if the criteria is satisifed then it should proceed with the upgraded level else degrade or if the inital level is beginner stay in the same level.