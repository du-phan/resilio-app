Advanced Marathoning — distilled reference for an AI coach

---

title: "Advanced Marathoning — distilled reference for an AI coach"source: "Pete Pfitzinger & Scott Douglas, Second Edition, Human Kinetics, 2009"version: "2024-05-24"

0. Core Philosophy

The Advanced Marathoning training methodology is built on a foundation of physiological principles designed to elicit maximal adaptation for experienced runners. It is not simply about accumulating mileage, but about applying specific training stresses in an intelligent, structured, and progressive manner. The core philosophy can be synthesized into the following key principles:

- Physiological Hierarchy: A high lactate threshold is the most critical physiological variable for marathon success, followed by running economy and VO2max. Training should be prioritized accordingly.
- Purpose-Driven Training: Every workout has a specific purpose aimed at developing a key physiological attribute. Training should be a targeted process, not a collection of random hard days.
- The Primacy of Recovery: Adaptation and improvement occur during recovery, not during the workout itself. Balancing training stress with adequate recovery is essential to absorb the benefits of hard work and prevent overtraining.
- Intelligent Volume: While increased mileage correlates with improved performance, it is subject to the law of diminishing returns. Mileage should be increased gradually and systematically, and it is a means to an end, not the goal itself.
- Specificity Matters: To race a marathon well, one must train specifically for its demands. This includes long runs to build endurance, lactate threshold runs to improve sustained speed, and marathon-pace runs to dial in the physical and mental requirements of race day.
- The Hard/Easy Principle: Training must be structured to alternate hard training days with easy or recovery days. This allows the body to recover from and adapt to the training stimulus.
- Periodization is Key: Training is organized into distinct phases (mesocycles), each with a specific focus. This structure ensures a logical progression of volume and intensity, culminating in a taper that allows for peak performance on race day.
- Consistency Over Spectacle: The cumulative effect of consistent, intelligent training over many weeks and months is what builds marathon fitness. A single heroic workout provides a far smaller stimulus than the sum of a well-executed training block.

1. Runner Profile Inputs (Data the AI Coach Should Collect)

Collecting a comprehensive profile for each runner is the strategic starting point for creating a safe, effective, and personalized marathon training plan. This data provides the necessary context to determine appropriate training paces, manage volume progression, set realistic goals, and identify potential risks before they lead to injury or overtraining.

Required:

- Recent Race Performance: A recent, all-out race time from a distance between 5K and a half marathon is essential for establishing initial training paces. A 15K or half marathon time is ideal for determining lactate threshold pace.
- Current Weekly Training Volume: The runner's average weekly mileage over the past several weeks. This serves as the baseline for any prescribed increases in training load.

Optional:

- Runner's Age: Age influences recovery rates and may require adjustments to the training plan.
- Training History: The number of years the runner has been training consistently and their previous peak mileage can indicate their capacity to handle higher training volumes.
- Past Injury History: A history of past injuries is crucial for tailoring mileage progression and identifying potential limiters to avoid re-injury.
- Lifestyle Factors: Information on sleep patterns, diet, and occupational or life stress is valuable, as these factors significantly impact recovery and the ability to adapt to training.
- Maximal Heart Rate (MHR): While paces are primary, an accurately determined MHR allows for heart-rate-based intensity monitoring, which is a useful tool for gauging effort.

Red flags / safety triggers:

- Low Iron Levels: A ferritin level below 25 ng/ml is a "definite red flag" that can significantly impair performance and should prompt a recommendation to consult a physician.
- Symptoms of Overtraining: Persistent fatigue, inability to complete workouts, elevated resting heart rate, disturbed sleep, or a decline in performance despite increased training.
- Symptoms of Illness: Any signs of systemic illness, especially those accompanied by fever, should trigger a pause in hard training. The immune system is suppressed for 12 to 72 hours after high-intensity or prolonged exercise.
- Limping or Progressively Increasing Pain: Any pain that alters running mechanics or worsens during a run is a sign of impending injury and warrants immediate cessation of the activity.

This data provides the foundational inputs for the training system. To apply it correctly, the coach and runner must share a precise understanding of the training vocabulary.

2. Canonical Vocabulary + Ontology

A precise, shared vocabulary is essential for an AI coach to deliver effective training. By clearly defining the purpose, rules, and constraints of each workout type, the coach ensures that every session is prescribed correctly and its function can be clearly explained to the runner. This eliminates ambiguity and empowers the runner to execute the training plan as intended.

Lactate Threshold (LT) Run (Tempo Run)

- definition: A continuous run of 20 to 40 minutes, preceded by a warm-up and followed by a cool-down, executed at the runner's lactate threshold intensity.
- purpose: To improve the lactate threshold, which is the most important physiological determinant of marathon performance. This workout trains the body to produce energy aerobically at a faster pace, increasing mitochondrial size and number, and enhancing aerobic enzyme activity.
- typical_use: A key "quality" workout performed regularly throughout a training plan to improve sustained speed endurance. It is preferable to LT intervals for marathoners because its continuous nature more closely simulates the demands of the marathon.
- hard_constraints:
  - Pace: Current 15K to half marathon race pace.
  - Heart Rate: 82-91% of max HR, or 77-88% of heart rate reserve.
  - Duration: 20 to 40 minutes for the tempo portion. Some schedules may include one longer tempo run up to 7 miles.
- common_mistakes: Running the tempo portion too fast, which causes rapid lactate accumulation and changes the workout's stimulus, making it counterproductive for marathon training.

VO2max Interval

- definition: A workout consisting of repeated running segments (intervals) of 600m to 1600m at high intensity, with recovery periods of jogging in between.
- purpose: To improve maximal oxygen uptake (VO2max), which is the maximal amount of oxygen your body can transport and use. While a secondary consideration for marathoners compared to LT, a higher VO2max raises the ceiling for all other aspects of aerobic fitness.
- typical_use: Used to strike a balance between being long enough to provide a powerful training stimulus and short enough to leave you fresh for your other important workouts of the week.
- hard_constraints:
  - Pace: Current 5K race pace.
  - Heart Rate: 93-95% of max HR, or 91-94% of heart rate reserve.
  - Interval Duration: 2 to 6 minutes (typically 800m to 1600m repeats).
  - Total Volume: The total distance of the intervals should be between 5,000 and 10,000 meters per session.
- common_mistakes:
  - Running the intervals too fast (e.g., at 1500m pace), which produces high lactate levels not relevant for marathoners and provides a smaller stimulus for VO2max improvement.
  - Performing VO2max sessions too frequently, detracting from more marathon-specific workouts like long runs and tempo runs.

Long Run

- definition: The cornerstone endurance workout, typically lasting from 15 to 22 miles, designed to improve glycogen storage, fat utilization, and musculoskeletal durability.
- purpose: To stimulate adaptations that enhance endurance, including increased glycogen storage, improved fat metabolism (glycogen sparing), and conversion of fast-twitch A fibers to have more slow-twitch characteristics. It also provides crucial psychological preparation.
- typical_use: Performed weekly, with the distance progressively increasing during the build-up phase of training.
- hard_constraints:
  - Pace: 10 to 20 percent slower than goal marathon pace.
  - Heart Rate: 74-84% of max HR, or 65-78% of heart rate reserve.
  - Maximum Distance: Should not exceed 22 miles (35 km), as longer runs provide dramatically increased recovery demands for minimal additional benefit.
- common_mistakes:
  - Running too slowly, which reinforces poor running mechanics and provides an inadequate simulation of marathon demands.
  - Running too fast, which leads to excessive fatigue that compromises other key workouts during the week.

Marathon-Pace Run

- definition: A medium-long or long run that includes a significant, continuous segment run at the runner's goal marathon pace.
- purpose: To provide precise physiological and psychological practice for race day. It improves running economy and efficiency at marathon pace and builds confidence in the runner's ability to maintain that pace.
- typical_use: Incorporated into long runs during the later stages of a marathon build-up to provide a highly specific training stimulus.
- hard_constraints:
  - Pace: Goal marathon pace.
  - Heart Rate: 79-88% of max HR, or 73-84% of heart rate reserve.
- common_mistakes: Treating it as a race and running faster than goal marathon pace, which can lead to excessive fatigue and compromise recovery.

General Aerobic Run

- definition: A steady run at a comfortable, conversational pace that makes up a significant portion of a runner's weekly mileage.
- purpose: To build and maintain baseline aerobic fitness, increase capillary density, and contribute to weekly training volume without adding excessive stress.
- typical_use: These are the standard "daily" runs that fall between key quality sessions and recovery days.
- hard_constraints:
  - Pace: Typically 15 to 25 percent slower than marathon race pace.
  - Heart Rate: 70-81% of max HR, or 62-75% of heart rate reserve.
- common_mistakes: Running them too hard, which turns them into "moderate" effort days and compromises recovery for the truly hard workouts.

Recovery Run

- definition: A very short, slow run performed the day after a hard workout to enhance recovery.
- purpose: To increase blood flow to the muscles, which helps clear metabolic waste products and deliver nutrients, thereby speeding up the recovery and adaptation process.
- typical_use: Performed on "easy" days, often as part of a double-run day or as the sole run following a hard session.
- hard_constraints:
  - Heart Rate: Below 76% of max HR, or below 70% of heart rate reserve. The effort should be genuinely easy.
- common_mistakes: Running too fast or too long, which negates the recovery benefit and adds unnecessary fatigue.

Strides

- definition: Short repetitions of fast but relaxed running, typically 80 to 120 meters long, with sufficient rest between each.
- purpose: To improve running economy and form by training muscles to eliminate unnecessary movements and maintain control at fast speeds. They also build leg power without generating significant lactate.
- typical_use: Often performed after a general aerobic or recovery run to gently introduce speed work without interfering with primary marathon workouts.
- hard_constraints:
  - Duration: 80 to 120 meters per repetition.
  - Intensity: Fast but relaxed, not an all-out sprint.
- common_mistakes: Sprinting instead of focusing on relaxed, efficient form.

Taper

- definition: The final phase of training, typically lasting three weeks, during which training volume is significantly reduced to allow the body to recover, adapt, and be fully rested for race day.
- purpose: To repair accumulated muscle damage, fully replenish glycogen stores, and bolster the immune system, leading to improvements in running economy and muscle strength for peak race-day performance.
- typical_use: The final 3 weeks of the marathon training schedule.
- hard_constraints:
  - Duration: 3 weeks is optimal for a marathon.
  - Volume Reduction: Reduce mileage by 20-25% in the first week, 40% in the second week, and 60% in the final week (6 days) before the race.
  - Intensity: Must be maintained. Continue to perform workouts at goal paces, but with reduced volume.
- common_mistakes: Reducing intensity along with volume, which can lead to a loss of fitness and feelings of sluggishness.

Having defined what the workouts are, the next step is to codify the logic for how and when they are applied.

3. Decision Rules (IF/THEN)

Decision rules provide the core logic for the AI coach, enabling it to translate runner data and training principles into a dynamic and responsive plan. These rules govern everything from initial pace selection to mid-plan adjustments, ensuring that the training stimulus is always appropriate for the runner's current fitness and circumstances.

Pace Selection Logic

- IF workout_type is 'VO2max', THEN pace is current_5K_race_pace.
- IF workout_type is 'Lactate Threshold', THEN pace is current_15K_to_half_marathon_race_pace.
- IF workout_type is 'Marathon-Pace', THEN pace is goal_marathon_pace.
- IF workout_type is 'Long Run', THEN pace is goal_marathon_pace + 10-20%.
- IF workout_type is 'General Aerobic', THEN pace is goal_marathon_pace + 15-25%.
- IF workout_type is 'Recovery', THEN effort is easy, with HR < 76% MHR.

Training Progression & Volume Management

- IF increasing weekly mileage, THEN limit the increase to a maximum of 10% per week OR no more than 1 mile per training session per week (e.g., a runner who runs 6 times per week can increase by up to 6 miles).
- IF increasing weekly mileage, THEN do so in steps: increase for one week, then hold at the new level for 2-3 weeks before increasing again.
- IF in a phase of increasing mileage (base building), THEN avoid hard speed work (VO2max intervals).
- IF adding miles to the schedule, THEN first add them to general aerobic runs, medium-long runs, or warm-ups/cool-downs.

Workout Substitution

- IF a running workout must be missed due to extreme weather or minor injury risk, THEN substitute with an appropriate cross-training activity.
- IF substituting a recovery run with cycling, THEN duration should be approximately 1.5x the planned run time (e.g., a 30-minute run becomes a 45-minute bike ride).
- IF substituting with water running, THEN emphasize interval workouts, as steady-state effort may be insufficient to maintain fitness. Note that target heart rate will be ~10% lower than for land running at an equivalent effort.
- IF substituting with cross-country skiing, swimming, or rowing, THEN acknowledge these are excellent low-impact aerobic alternatives for maintaining cardiovascular fitness.

Scaling for Missed Training

- IF <10 days of training are missed, THEN resume the schedule where the runner would have been.
- IF 10-20 days are missed and the marathon is less than 8 weeks away, THEN advise the runner to revise their goal.
- IF >20 days are missed, THEN advise the runner to revise their goal, regardless of the time remaining.
- IF a VO2max workout was missed, THEN advise the runner to slow the pace of the next VO2max session to reflect the lost time.

These rules provide the logic for adapting the plan; the next step is to define the structure of the key workouts themselves.

4. Workout Constructors

Workout constructors serve as standardized templates that the AI coach uses to build specific, complete training sessions. By populating these templates with values derived from the runner's profile and the decision rules (e.g., pace, duration), the coach can generate clear, actionable workouts that adhere to the program's methodology.

Lactate Threshold (Tempo) Run

- Inputs_needed: LT_PACE, TEMPO_DURATION (e.g., 5 miles), total_daily_mileage (e.g., 10 miles).
- Step-by-step_template:
  1. Warm-up: Run for 15-20 minutes (or 2-3 miles) at an easy, aerobic pace.
  2. Main Set: Run for TEMPO_DURATION at LT_PACE.
  3. Cool-down: Run for the remaining mileage (at least 10-15 minutes) at an easy, recovery pace.
- Guardrails: The core tempo segment must not be shorter than 20 minutes or longer than 40 minutes (or ~7 miles). The pace should be strictly controlled; it is not a race effort.
- Variations: The workout can be performed on a moderately hilly course to simulate race-specific terrain, adjusting effort to maintain the correct intensity zone.

VO2max Interval Run

- Inputs_needed: VO2_PACE, INTERVAL_DISTANCE (e.g., 1200m), NUM_REPETITIONS (e.g., 5), total_daily_mileage.
- Step-by-step_template:
  1. Warm-up: Run for 2-3 miles at an easy, aerobic pace, followed by a few strides.
  2. Main Set: Perform NUM_REPETITIONS x INTERVAL_DISTANCE at VO2_PACE. Recovery between intervals should be a slow jog, typically 50-90% of the interval time.
  3. Cool-down: Run for 2-3 miles at an easy, recovery pace.
- Guardrails: Total volume of intervals must not exceed 10,000 meters. The pace is current 5K race pace, not faster. This workout is physiologically stressful; ensure adequate recovery before and after.
- Variations: The workout can be performed on a moderately steep hill to simultaneously build strength and cardiovascular fitness.

Long Run (with Marathon-Pace variation)

- Inputs_needed: TOTAL_LONG_RUN_DISTANCE (e.g., 20 miles), LONG_RUN_PACE (10-20% slower than MPACE), and optionally MPACE_DISTANCE (e.g., 10 miles) and MPACE.
- Step-by-step_template:
  1. Easy Start: Run an initial segment at LONG_RUN_PACE (e.g., 2-5 miles).
  2. Main Set:
  - Standard Long Run: Continue for the TOTAL_LONG_RUN_DISTANCE at LONG_RUN_PACE.
  - Marathon-Pace Variation: Run MPACE_DISTANCE at MPACE.
  3. Cool-down: Run the remaining distance at LONG_RUN_PACE.
- Guardrails: Total distance must not exceed 22 miles. Marathon-pace segments should be introduced strategically in the weeks leading up to the taper and should feel controlled, not like a race.
- Variations: The primary variation is the inclusion of a marathon-pace segment. The run should also be used to practice and refine race-day nutrition and hydration strategies.

With the individual workouts defined, the final step is to understand how they are assembled into a coherent training plan over weeks and months.

5. Week/Season Structure

A successful marathon plan is more than just a list of workouts; it is a strategically structured journey. The principle of periodization—dividing the training season into distinct phases (mesocycles)—ensures a progressive and logical application of training stress. This approach allows for gradual adaptation, minimizes the risk of burnout or injury, and orchestrates a peak in fitness that coincides perfectly with race day.

Training Phases (Mesocycles)

The marathon training plan is typically broken down into four distinct phases, each with a specific purpose that builds upon the last.

1. Base Building / Endurance: This initial phase focuses on gradually increasing mileage and establishing a strong aerobic foundation. The intensity is relatively low, with the primary emphasis on long runs and general aerobic runs.
2. Peak Mileage / Lactate Threshold: In this phase, training volume reaches its peak. The focus shifts to improving lactate threshold through regular tempo runs while maintaining high mileage. This is the most demanding phase of training.
3. Pre-Taper / Race Preparation: Mileage begins to decrease slightly from its peak. The focus is on race-specific workouts, such as long runs with extended marathon-pace segments and tune-up races, to sharpen fitness and build confidence.
4. Taper: This final 3-week phase is dedicated to recovery and peaking. Training volume is reduced dramatically while intensity is maintained through shorter, faster workouts. The goal is to arrive at the starting line feeling fresh, sharp, and fully recovered.

The Hard/Easy Principle

The foundation of weekly scheduling is the balance between stress and recovery. Hard training days (long runs, LT runs, VO2max intervals) provide the stimulus for adaptation, while easy days (recovery runs, general aerobic runs, rest) allow that adaptation to occur. There are two valid patterns for structuring this:

1. Alternating Hard/Easy: The most common structure, where each hard day is followed by at least one easy day (e.g., Hard-Easy-Hard-Easy).
2. Back-to-Back Hard Days: A more advanced structure where two consecutive hard days are followed by two or more recovery days (e.g., Hard-Hard-Easy-Easy). This pattern is particularly useful during race weeks, as it allows for an extra recovery day before the race itself.

Tapering Principles

An optimal 3-week marathon taper is critical for realizing the full benefit of months of training. It operates on several non-negotiable principles:

- Duration: The taper must begin 3 weeks before the marathon.
- Maintain Intensity: Continue to run at your goal paces during workouts. The purpose is to stay sharp, not detrain.
- Reduce Mileage Systematically: The primary change is a significant reduction in training volume.
  - Week 1 (3 weeks out): Reduce total weekly mileage by 20-25% from your peak.
  - Week 2 (2 weeks out): Reduce total weekly mileage by 40% from your peak.
  - Week 3 (Race Week): Reduce mileage by 60% from your peak in the 6 days leading up to the race.
- Prioritize Recovery: Make recovery days exceptionally easy or take extra days off. Eliminate all non-essential training stress, including strength training in the final 10 days.

Incorporating Tune-Up Races

Tune-up races serve the dual purpose of providing objective feedback on current fitness and offering crucial mental preparation for the rigors of racing. They should be planned strategically within the training schedule.

- Longer Races (15K to 25K): These provide the greatest physiological and psychological benefit but require significant recovery. They should be treated as a "10-day block" consisting of a 4- to 6-day mini-taper, the race itself, and several days of recovery before the next hard session.
- Shorter Races (8K to 12K): These require less recovery. They can either be approached as an all-out effort done on tired legs (as a training stimulus) or with a short mini-taper to assess fitness and boost confidence.

The following examples illustrate how these principles and constructors come together in practice.

6. Minimal Examples

The following are minimal, complete examples of workout sessions generated using the defined constructors and vocabulary.

- Lactate Threshold Workout: 10 miles total, including a 5-mile tempo run.
  1. Warm-up: 3 miles easy.
  2. Main Set: 5 miles at LT_PACE.
  3. Cool-down: 2 miles easy.
- VO2max Interval Workout: 9 miles total, including 5 x 1000m intervals.
  1. Warm-up: 2.5 miles easy, with strides.
  2. Main Set: 5 x 1000m at VO2_PACE, with recovery jogs of 50-90% of the interval time between each.
  3. Cool-down: 2.5 miles easy.
- Marathon-Pace Long Run: 20-mile long run with a 10-mile marathon-pace segment.
  1. Easy Start: 5 miles at a comfortable long-run pace.
  2. Main Set: 10 miles at MPACE.
  3. Cool-down: 5 miles at a comfortable long-run pace.
