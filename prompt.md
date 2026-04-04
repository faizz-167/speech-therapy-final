Therapist Account : 

Therapist Registration page : Name, email, password, years of experience
Login  page : email and password

Therapist Login will have the following pages : 

1. Dashboard page - Complete metrics about the patient count, patient's progress and any clinical verification needed for a patient
2. Patient Registration page - The therapist will register for a patient : The necessary details for patient registration includes : patient name, email, age, gender, defect they have(multiple choice based on our predefined set of defects). Once a patient,  the patient details will be displayed as a card view in the same page. By clicking a particular patient's card view, we can have the following details : baseline assessment scores, ai therapy plan page, progress of the patient. 
The AI therapy plan should only generate after the patient performs the baseline assessment, coz it considers two kind of data : the data which the therapist provides about the patient and the metrics from the baseline assessment. This ai plan should provide exercise based the level(e.g easy, medium, advanced) which is calculated from the baseline assessment scores.

AI therapy plan will generated for a whole week starting from the day of registration, the therapist will analyse the task for the whole week and they can add, update or delete the task. They can also drag and move the task to assign it to a different day. When the therapist adds a new task, then the task name should be displayed as a drop down(We have defined the tasks for that particular defects, from that only the dropdown should display), the level(easy, medium or advanced). This add option will be applicable for all the days in the week. Once the therapist approves the task plan. This will be reflected in the patient's task page.

The therapist can also see the complete progress of the patient and also in between if the metrics seems to be down, they can modify the task plan accordingly.

Therapist Profile page : It displays all the necessary details about the  therapist and also provide the therapist code for the patients to register which will map the patients to the therapist

Patient Account : 

Patient Registration Page : Patient name, age, email, gender, therapist code and password.
Patient Login page : email and password

Patient's home page : It should display the today's tasks and also initially, it should display the baseline assessment to be taken by the user.
Tasks page : It should display the completed task, pending or in progress tasks. And the task will be generated for the whole week, but in the patient's task page it should display the everyday's task alone, it should not display the whole week task all at once.
Progress Page : It will display about the metrics about the patient's completion and accuracy levels and some metrics like where do they want to concentrate on more.
Patient's Profile Page : A profile of the user will be displayed.


Flow of the Project : 

Therapist will be register with their details which is mentioned above and it will be stored in the database. Once registered, then can login with the email and password. The dashboard should fetch and display : Number of users, Notification for accepting the patient's invite. Then, in the therapist portal, we have a page for the patients. The base template for the patient registration are Name, age, gender, email, the defect the patient undergoes. The base template which should display after the registration are baseline assessment score, ai therapy plan and progress In that page, it should display all the patients which are mapped to the therapist. And also the page should provide the option of "Adding a patient with the details". Once registered, we check the details as per the base template. Now, the patient will register with the above mentioned details. Once registered, a notification will be sent to the therapist for their approval, this will prevent the patient's login before the therapist registers them. Because the baseline assessment should be based on the defect the therapist registers and also for the task mapping, we need to know about the patient's defect and also the baseline assessment scores to decide the level of range where we should start the task(i.e, from easy or medium or advanced). The baseline assessment should fetch the task ezercise from the database by filtering with the age and the defect they have because we have created the baseline task mapped with the defects. Once baseline is completed by the user, it should reflect in the therapist portal, to start with the process of ai plan creation. 

The therapist will verify the baseline assessment status : Once it is completed, then we'll start with the process of ai therapy plan creation for a week. The logic for creation of ai plan  : It should create a plan from the day of plan creation upto the end of the week. Then based on the baseline scores, we have the level of range (easy or medium or advanced), based on the user (child or adult) and the defect, we should filter the defects from the db and provide the most appropriate task for the week. If the user is too basic, then give basic task or else upgrade them. The plan should be generated for the whole week and it should be displayed to the therapist. The therapist can perform the CRUD operations like adding a task or updating or deleting it. The task plan for the week should be displayed as a "Kanban Board". Therapist can drag and drop the task between the days accordingly. When adding a new task, we should give the option of the task names which is mapped to the defect by fetching the task which is mapped to the defect from the database(by analysing the defect, task, defect mapping, etc., tables). A therapist can approve or reject a plan. Once approved, the patient portal will display the task which is assigned to the particular day. For each day, everyday's task will be dislayed to them. the therapist can check the progress of each patient in the progress section and by the end of week, the system should create a report based on the task and accuracy.4


Patients will be register with their details which is mentioned above and it will be stored in the database. Once registered, an approval notification will be sent to the therapist portal,  when therapist is approved we can login with the email and password. The dashboard should fetch and display : Today's task and Initally it will display and remind the patient to attend the baseline assessment. 

The logic of baseline assessment : 

The baseline assessment should be conducted based on the defect the user is undergoing which is registered and stored in the database. Fetch the defects of the patient and map the task exercise in the database and provide the particular assessment for them. For each task exercise, calculate the word accuracy, phenome accuracy, fluency score, speech rate score, hesitation and engagement scores, the appropriate formulas for calculating this is given in the md file, the system should calculated the fusioned final score from the speech and engagement scores and store it in the database. Once all task is completed, calculate the averaged final score of each task exercise and provide that to the therapist portal where it will display the baseline scores for each patient. This averaged score will have a logic for choosing the level of task to start with the task exercise, the range should be 50 - 70 : "easy" range, 70-80 : "medium" range and above 80 : "advanced" range. Then this data should be stored in the code and it should be given to the therapist function for creating the ai therapy plan. The plan should take this level of range, the defect and fetch the task name and its details and prepare a task plan. 

Once the therapist approves, it should show to the user. The user will have a task page, where they can view all completed task, pending tasks and progress tasks which will show if any pending task (left from previous days) are there to make them complete. There will be a progress page, where the user can get a accuracy level and a positive feedback on where to improve on. 

Task Exercise logic :

There are different task available for each defects in the database. After fetching the task as per the ai plan or on the baseline, the template should be : A recorder should record the speech of the user and calculate the following : WA = Word Accuracy, PA = Phoneme Accuracy, FS = Fluency Score, SRS = Speech Rate Score, DR = Disfluency Rate, PS = Pause Score, BS = Behavioral Score, ES = Emotion Score, RL_score = Response Latency Score, TC = Task Completion, AQ = Attempt Quality . Then it should be stored in the database with the task name, level and all these accuracy values and the final scores. 

For each task : show the transcript and all accuracy values and final score for each. // This is for testing and can remove it for future.

For the baseline assessment, we will take the average of the scores and provide to the therapist for the future ai creation plan.
For the task exercise after plan creation, we will store the task exercise and its accuracy in the database tables. Once the user is well perfomed on a particular task category, the system will move on to the next level right. If a task category is completed by the user, then we can calculate the average score and store it in the table. Also for the whole week, if the user attends the same task twice or thrice, we have store each task exercise accuracy and also the average of the same task.

Example scenario : 

If I'm attending a word reputation task today but I failed to complete all the tasks but I complete the today's task, then again on the Saturday I am getting this task again by having some advancement in the level from medium to advanced. Then If I also completed the advanced level then the db should store the each exercise task accuracy. If I complete the easy, medium and advanced range, for the task category set it should get average value and store them in the table. the table should have the task name, exercise and its all accuracy values and we should have a column extra as what are the pending number of task which is available for this exercise, so if a task contains some 6 level on the whole and if I have completed only four then it should not calculate the complete accuracy it will be it should only calculate the per week accuracy and when the user completes the complete number of tasks like when I complete 6 task then you should calculate the overall average accuracy of the task category and it should stored in the separate table like task completion for each task categories. 

This will generate a report to the patient and therapist to know about the areas where the user got well trained. The weekly report for the therapist will contain the data task name, exercise provided, the accuracy for that task and if same task was given twice or more than that, the system should display them at the end.

The whole process will be performed for each week and if the user is well trained on all exercise, then the therapist can stop the process.