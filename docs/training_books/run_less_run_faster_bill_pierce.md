Run Less Run Faster — distilled reference for an AI coach

The "Run Less, Run Faster" (FIRST) philosophy offers a strategic, time-efficient, and science-backed training method for runners of all levels. In a world where time is a premium, this approach contrasts sharply with traditional high-mileage plans by prioritizing the quality and intensity of each workout over sheer volume. The program is designed to maximize performance gains while systematically minimizing the risk of overtraining and injury, enabling runners to achieve their goals without sacrificing their job, health, or family life.

The core tenets of the FIRST training program can be synthesized into the following principles:

- Assert that training intensity is the single most important factor for improving running fitness, mandating a focus on quality over the simple accumulation of miles.
- Center the training week on a "3plus2" structure. The foundation of the program is three specific, high-quality runs and two complementary cross-training workouts each week.
- Mandate that every run is a "Training with Purpose" session. Each of the three key runs has a specific, individualized pace and distance goal designed to elicit a targeted physiological adaptation.
- Utilize three distinct types of key runs to systematically improve performance. The program combines Track Repeats (for leg speed and VO2 max), Tempo Runs (for lactate threshold), and Long Runs (for endurance).
- Execute long runs at a challenging, purposeful pace. Unlike in traditional programs, long runs are performed at a faster pace to better prepare the body and mind for race-day intensity.
- Incorporate non-weight-bearing cross-training. Activities like cycling, swimming, and rowing enhance cardiorespiratory fitness and promote active recovery without the repetitive impact stress of additional running.
- Recognize rest and recovery as fundamental components of training. Adequate recovery is not an afterthought but a critical element that enables physiological adaptation and prevents the onset of overtraining.
- Base all training paces on a recent, real-world race performance. A recent 5K race time is used as the sole determinant for calculating all key training paces, ensuring appropriate and effective training intensity.
- View supplemental work as essential. Strength training and flexibility drills are integrated as vital components for injury prevention, maintaining proper form, and enhancing running economy, not as optional add-ons.

Applying this philosophy effectively begins with gathering specific data about the individual runner to create a personalized and safe training plan.

1. Runner profile inputs (data the AI coach should collect)

A structured runner profile is the foundation for personalizing the FIRST program. Collecting comprehensive and accurate data is crucial for setting training parameters that are safe, realistic, and effective. This initial assessment ensures that the prescribed paces and distances are appropriate for the runner's current fitness level and goals.

- Required
  - Current Race Performance: A recent race time, ideally from a 5K, is non-negotiable.
    - Rationale: This metric is the sole determinant for calculating all key training paces (Track Repeats, Tempo Runs, and Long Runs) using the program's established tables. It ensures that training intensity is perfectly matched to the runner's current fitness.
  - Goal Race Distance: The target event (5K, 10K, Half-Marathon, or Marathon).
    - Rationale: This determines which 12- to 16-week training schedule to apply, dictating the specific progression of distances and workout structures leading up to the race.
- Optional
  - Age and Gender: The runner's age and gender.
    - Rationale: This data is useful for setting realistic goals and can be used to apply age-graded performance standards (as detailed in the book's appendices) to compare performances across different age groups.
  - Running History / Base Mileage: A summary of recent running volume and experience.
    - Rationale: The program requires a pre-existing running base. For 5K/10K plans, a base of approximately 15 miles per week for 3 months is recommended; for the marathon plan, this increases to about 25 miles per week.
  - Access to Facilities: Confirmation of available training locations and equipment.
    - Rationale: The availability of a 400m track, hills, and non-weight-bearing cross-training equipment (such as a stationary bike, swimming pool, or rowing machine) will influence how specific workouts are implemented.
- Red flags / safety triggers
  - Medical History: Any existing medical conditions or if the runner is over 40 years of age.
    - Rationale: These factors mandate physician clearance before the runner begins this or any strenuous exercise program.
  - Overtraining Symptoms: Presence of prolonged fatigue, irritability, sleep disturbances, increased susceptibility to colds, or a decline in training performance.
    - Rationale: The presence of these symptoms is a critical trigger to immediately advise rest or a significant reduction in training load to prevent further physical and mental decline.
  - Injury Symptoms: Any pain that develops during a run or worsens with activity.
    - Rationale: This is a trigger to reduce the intensity and distance of the workout, modify it, or stop entirely. Key injuries to monitor for include plantar fasciitis, Achilles tendinitis, and runner's knee.
  - Heat-Related Distress: Symptoms such as headaches, disorientation, muscle spasms, or a cessation of sweating during a workout.
    - Rationale: These are critical signs of a serious heat injury and are a trigger to stop the workout immediately, seek shade, and hydrate.

With a validated runner profile, the coach must now operate using the program's precise and unambiguous vocabulary.

2. Canonical vocabulary + ontology

A precise vocabulary is essential for a coaching system to construct workouts and provide clear, purpose-driven explanations. This section defines the core components of the FIRST 3plus2 program, ensuring the AI coach can communicate effectively and build training sessions that align perfectly with the program's methodology.

- Key Run #1: Track Repeats
  - definition: A workout consisting of running a series of specific distances (e.g., 400m, 1000m, 1600m) at a fast, prescribed pace, interspersed with recovery intervals of walking or jogging.
  - purpose: To improve leg speed, running economy, and maximal oxygen consumption (VO2 max), which are critical for enhancing race performance.
  - typical use: Performed once per week, ideally on a 400m track. A complete session includes a warm-up, the main set of repeats, and a cool-down.
  - hard constraints: The specific paces for the running intervals and the durations of the recovery periods are strictly determined by the runner's current 5K race time, as specified in the program's pace tables.
  - common mistakes: Running the repeats faster than the prescribed pace, which leads to excessive fatigue and compromises the quality of subsequent key workouts; cutting the recovery intervals short, preventing adequate preparation for the next repeat.
- Key Run #2: Tempo Run
  - definition: A workout that involves a sustained effort of continuous running at or near the lactate threshold pace for a specified distance or duration.
  - purpose: To increase the body's ability to clear lactate from the blood, which raises the lactate-threshold running pace and enhances the ability to sustain harder efforts for longer periods.
  - typical use: Performed once per week. A standard session consists of a warm-up, a continuous tempo segment (e.g., 3-10 miles), and a cool-down.
  - hard constraints: The tempo pace is derived directly from the runner's current 5K time. The tempo portion is typically 3-5 miles for 5K/10K training plans and extends up to 8-10 miles for marathon training plans.
  - common mistakes: Running the tempo segment too fast, effectively turning it into a race effort rather than a controlled, sustained workout; failing to complete the warm-up or cool-down, which are essential for preparation and recovery.
- Key Run #3: Long Run
  - definition: The longest run of the training week, conducted at a pace that is significantly faster and more challenging than the typical "easy" or "conversational" long run found in most other training plans.
  - purpose: To improve endurance, muscular durability, and mental toughness. It also serves as a crucial opportunity to practice and refine race-specific fueling and pacing strategies.
  - typical use: Performed once per week, usually on a weekend to allow for adequate time. The total distance of the run progressively increases throughout the 16-week training plan.
  - hard constraints: The pace is prescribed based on goal race pace, with offsets that vary throughout the plan (e.g., ranging from Marathon Pace + 45 seconds/mile down to Marathon Pace + 15 seconds/mile). The plan includes up to five long runs of 20 miles for marathon preparation.
  - common mistakes: Running these faster than the prescribed pace in an attempt to "bank" time; starting out too fast instead of easing into the first few miles before settling into the target pace.
- Cross-Training (XT)
  - definition: Non-running aerobic exercise performed 2-3 times per week, typically on the days between the key runs.
  - purpose: To enhance overall cardiorespiratory fitness, promote active recovery by increasing blood flow to muscles, and reduce the risk of overuse injuries by avoiding the repetitive impact of additional running.
  - typical use: Sessions are prescribed based on time and intensity (e.g., 45 minutes with a "tempo" or "hard" effort). Recommended modes are non-weight-bearing.
  - hard constraints: The program explicitly recommends non-weight-bearing activities such as cycling, swimming, or rowing. It advises against weight-bearing activities like the elliptical or stair climber. Supplemental programs like yoga or P90X are beneficial for strength and flexibility but do not replace these core aerobic XT sessions.
  - common mistakes: Performing the cross-training session at too low an intensity, treating it as a pure "easy day" when a "tempo" or "hard" effort is prescribed; substituting the workout with a weight-bearing activity, which negates the recovery benefits.

These canonical terms are the building blocks for the operational logic that dictates all coaching decisions.

3. Decision rules (IF/THEN)

This section defines the logical core of the AI coach. These IF/THEN rules translate the FIRST philosophy and its core components into concrete, automated coaching decisions. They govern workout selection, progression, real-time adaptation, and essential safety management, ensuring the runner receives a responsive and intelligent training experience.

- Pace Selection & Progression
  - IF a runner provides a valid recent 5K race time, THEN use the program's official pace tables to set all initial training paces for the three key runs (Track Repeats, Tempo, Long Run).
  - IF a runner consistently completes all three key runs for a given week at the prescribed paces without excessive strain or signs of overtraining, THEN proceed with the next scheduled week of the training plan.
  - IF during a 16-week plan, a runner reports that all key workouts have become consistently easy to complete, THEN recommend using a faster 5K reference time (either from a new race or a realistic estimate) to recalculate and increase all training paces.
- Workout Substitution & Modification
  - IF the goal race course is described as hilly, THEN advise the runner to incorporate hills into their Tempo and Long runs, emphasizing the need to maintain a constant effort rather than a constant pace (i.e., running slower uphill and faster downhill).
  - IF a runner reports a minor injury symptom (e.g., new soreness that is not debilitating), THEN first advise reducing the distance and pace of the next key run. IF the symptom persists or worsens, THEN advise reducing run frequency and substituting the missed run with non-weight-bearing cross-training, such as deep water running.
  - IF a runner must miss a workout due to unforeseen circumstances (e.g., weather, time constraints), THEN instruct them to prioritize completing the three key runs over the cross-training sessions. Advise against trying to "make up" for a missed key run by doubling up workouts later in the week.
- Scaling & Onboarding
  - IF a user is a new runner or lacks the required mileage base (approx. 15 miles/week for 5K/10K; 25 miles/week for marathon), THEN do not start a FIRST training plan. Instead, prescribe a base-building phase of at least 3 months with the goal of consistently reaching the required weekly mileage.
  - IF a runner is returning from a full marathon, THEN enforce the mandatory recovery protocol: one full week of no running, followed by one week of only easy runs, followed by a third week of workouts at no more than 90% effort before resuming a full training schedule.
  - IF a runner is returning from a half marathon, THEN enforce the mandatory two-week recovery protocol: In the first week, take a full rest day after the race and substitute Key Runs #1 and #2 with easy runs. In the second week, the long run should be half of its normal distance at an easy pace before resuming the full training schedule.

These rules are used to populate and adapt a set of standardized workout templates, ensuring each session is structured and effective.

4. Workout constructors

Workout constructors serve as standardized templates that the AI coach can populate with specific paces, distances, and durations based on the runner's profile and the program's decision rules. This ensures that every session is structured, purposeful, and executed within safe and effective parameters, delivering a consistent training experience.

- Constructor for: Key Run #1 (Track Repeats)
  - Inputs needed: RUNNER_5K_TIME (to determine pace), WEEKLY_PLAN_SCHEDULE (to determine rep distance, count, and recovery interval).
  - Step-by-step template:
    1. Warmup: 10-15 minutes of easy running, followed by 2-4 x 100m strides.
    2. Main Set: Perform [Rep Count] x [Rep Distance] at [Calculated Repeat Pace] with [Recovery Interval] of easy jogging or walking between each repetition.
    3. Cooldown: 10-15 minutes of easy running.
  - Guardrails:
    - Pace Adherence: The workout is flagged for review if repeat times are consistently more than 2-3 seconds per 400m faster than [Calculated Repeat Pace].
    - Recovery Interval: The full [Recovery Interval] is mandatory; do not allow the runner to start the next repeat early.
  - Variations: The training plans systematically vary the [Rep Count] and [Rep Distance] from week to week to provide progressive overload. Form drills, such as "butt kicks" and "high knees," can be incorporated into the warm-up strides.
- Constructor for: Key Run #2 (Tempo Run)
  - Inputs needed: RUNNER_5K_TIME (to determine pace), WEEKLY_PLAN_SCHEDULE (to determine tempo distance).
  - Step-by-step template:
    1. Warmup: 1 mile of easy running, with the pace gradually increasing toward the end to approach tempo pace.
    2. Main Set: Run [Tempo Distance] continuously at [Calculated Tempo Pace].
    3. Cooldown: 1 mile of easy running.
  - Guardrails:
    - Distance: Tempo distance is typically 3-5 miles for 5K/10K plans and progresses to 8-10 miles for marathon plans.
    - Effort Level: Reinforce to the runner that the prescribed pace should feel "comfortably hard." Post-workout feedback should ask if the effort felt sustainable or like a race effort.
  - Variations: If performed on a hilly course, the runner should be instructed to maintain [Tempo Effort] rather than a strict [Tempo Pace], allowing the pace to slow on uphills and quicken on downhills while keeping exertion constant.
- Constructor for: Key Run #3 (Long Run)
  - Inputs needed: RUNNER_5K_TIME (to determine pace), WEEKLY_PLAN_SCHEDULE (to determine total distance).
  - Step-by-step template:
    1. Main Set: Run [Total Long Run Distance] at an average pace of [Calculated Long Run Pace].
    2. Instruction: Advise the runner to start the first 1-2 miles slightly slower than the target pace, settle into the prescribed pace for the main portion of the run, and aim to finish the final couple of miles strong.
    3. Cooldown: 10 minutes of easy walking and static stretching. Instruct the runner that consuming a recovery or sports drink during this 10-minute window significantly aids recovery.
  - Guardrails:
    - Distance: For marathon training, the maximum long run distance prescribed in the plans is 20 miles.
    - Pacing: The pace should be challenging but sustainable, not an all-out effort. Flag workouts where average pace deviates significantly from the target.
  - Variations: The run can be performed on terrain that mimics the goal race course (e.g., rolling hills, flat roads) to meet the principle of specificity.

These individual workouts are organized into a coherent weekly and seasonal structure to produce the desired cumulative training effect.

5. Week/season structure

The success of the FIRST training program relies on its macro-level organization, which consistently arranges periods of stress and recovery. This predictable weekly rhythm is mapped across a full 12- to 16-week training cycle, culminating in peak performance for a goal race. Proper seasonal planning then ensures long-term progress and sustainability.

- Standard Weekly Layout
  - The recommended 7-day schedule is designed to distribute the three key runs and two cross-training sessions to maximize recovery and adaptation between high-intensity efforts. A typical week is structured as follows:
    - Day 1: Cross-Training #1 (Moderate or Hard Effort)
    - Day 2: Key Run #1 (Track Repeats)
    - Day 3: Cross-Training #2 (Moderate or Hard Effort)
    - Day 4: Key Run #2 (Tempo Run)
    - Day 5: Rest
    - Day 6: Key Run #3 (Long Run)
    - Day 7: Rest or Optional Light Cross-Training
- Planning from a Goal Race
  - All training plans are designed to be implemented by working backward from the goal race date. The runner selects the appropriate 16-week plan for their target distance (5K, 10K, Half-Marathon, or Marathon), and the schedule is aligned so that Week 16 concludes on race day.
- Seasonal Focus
  - The year should be divided into distinct training cycles to allow for proper focus and recovery. Training for multiple marathons back-to-back is strongly discouraged. A recommended strategy is to focus on shorter distances like the 5K and 10K in one season (e.g., spring) to build speed, and then target a longer distance like a half-marathon or marathon in another season (e.g., fall).
- Tapering Principles
  - The taper is a planned reduction in training volume during the final week before a goal race to shed fatigue and maximize performance.
  - The key rules for the race-week taper are explicit: skip all cross-training sessions. The three key runs are significantly reduced in volume and/or intensity, as specified in the final week of the training schedule. The primary goal of the taper is to arrive at the start line feeling rested, healthy, and fully prepared to race.

The following examples illustrate how these principles and constructors come together to form complete, purposeful workout sessions.

6. Minimal examples

This section provides concrete examples of complete workout sessions as they would be prescribed to a runner. These examples utilize placeholders for paces (e.g., ST_PACE, LT_PACE), which the AI coach would populate with specific, calculated times based on an individual runner's profile and current 5K performance.

Example 1: Marathon-focused Track Workout (Mid-plan)

- Type: Key Run #1
- Warmup: 15 minutes easy run, followed by 4 x 100m strides with "butt kicks" incorporated into the third stride.
- Main Set: 3 x 1600m at ST_PACE with a 400m easy jog recovery between each repetition.
- Cooldown: 15 minutes easy run.

Example 2: 10K-focused Tempo Workout

- Type: Key Run #2
- Warmup: 1 mile easy run, gradually increasing pace.
- Main Set: 3 miles continuous run at LT_PACE.
- Cooldown: 1 mile easy run.

Example 3: Marathon Long Run (Advanced)

- Type: Key Run #3
- Main Set: 18 miles at an average pace of MP_PACE + 30 sec/mile.
- Cooldown: 10-minute walk followed by static stretching for hamstrings and calves.

Example 4: Standard Cross-Training Session

- Type: Cross-Training #1
- Mode: Stationary Bike
- Workout: 10 min easy spin (warmup), followed by 20 min sustained "Tempo" effort, concluding with a 10 min easy spin (cooldown).

Example 5: Hilly Course Tempo Simulation

- Type: Key Run #2
- Location: Rolling hills course.
- Warmup: 1 mile easy run on flat or gently rolling terrain.
- Main Set: 4 miles maintaining a constant "Tempo Effort." Advise the runner that their pace will naturally slow on uphills and quicken on downhills.
- Cooldown: 1 mile easy run.
