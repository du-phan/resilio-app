Faster Road Racing: 5K to Half Marathon — distilled reference for an AI coach

Source: Pete Pfitzinger & Philip Latter, 2015, Human Kinetics Version: October 26, 2023

---

0. Core Philosophy

- Training success is built on consistency, staying healthy, and long-term perseverance.
- A long, patient, and strategic aerobic base buildup is the foundation for all successful training.
- Race-specific fitness is achieved through targeted training periods that follow the base-building phase.
- Training must balance the stress of hard workouts with adequate recovery to allow for physiological adaptation (supercompensation).
- There are four primary types of running training: endurance runs, lactate threshold runs, VO₂max intervals, and speed work.
- Intelligent training strategically combines the primary workouts with general aerobic and recovery runs.
- Supplementary training—including cross-training, strength work, and flexibility—is essential for improving performance and preventing injury.
- Long-term development over a running career requires a gradual increase in training stimulus from year to year.
- Each workout has a specific physiological purpose; the most effective training is not always the most physically demanding.
- There are no secrets or shortcuts in distance running, only the application of sound principles.

1. Runner Profile Inputs (Data the AI coach should collect)

- Required:
  - Goal Race Distance: The specific event the runner is training for (5K to half marathon).
  - Recent Race Performances: Times from recent races (ideally within the last 6-8 weeks) to establish accurate training paces.
  - Current Weekly Mileage: The average weekly running volume the athlete has consistently maintained for the past 4-6 weeks.
  - Age: Critical for determining recovery needs, especially for masters runners (age 40+).
- Optional:
  - Running History: Years of experience, past training volume, previous injuries, and training pitfalls.
  - Typical Running Surfaces: Predominant surfaces used for training (e.g., road, track, trails, grass) to manage impact stress.
  - Access to Facilities: Availability of a track for interval workouts, hills for strength and intensity, and a gym for supplementary training.
  - Weight: For calculating nutrition and hydration needs.
- Red Flags / Safety Triggers:
  - Symptoms of Overreaching/Overtraining:
    - Persistent fatigue or low energy levels.
    - Increased general muscle soreness lasting more than a few days.
    - Reduced quality or duration of sleep for three or more consecutive days.
    - Irritability, mood disturbances, or loss of enthusiasm for training.
    - Elevated waking heart rate (more than 5 beats per minute higher than usual for two or more consecutive days).
    - Reduced appetite or unexplained weight loss.
    - An increased sense of exertion at a given training pace.
  - Symptoms of Illness:
    - Any illness symptoms "below the chest," such as lung congestion.
  - Pain or Injury:
    - Any reported pain at a known or new injury site during or after a run.
    - Alteration of running biomechanics to compensate for pain.

2. Canonical Vocabulary + Ontology

Endurance Runs (Long Runs)

- Name: Endurance Runs (Long Runs)
- Plain Definition: Any run where the primary purpose is to improve a runner's endurance.
- Purpose: To build a solid endurance base, allowing the runner to maintain a faster pace for a longer time. Stimulates increased fat utilization, glycogen storage, and capillary density, while making fast-twitch muscle fibers more fatigue-resistant.
- Typical Use: A cornerstone of training for all distances from 5K to half marathon, typically performed once per week. The distance is gradually increased during a training cycle.
- Hard Constraints:
  - Pace: 20-33% slower than 10K race pace, or 17-29% slower than 15K to half-marathon pace.
  - Intensity: Approximately 74-84% of maximal heart rate (HRmax) or 65-78% of heart rate reserve (HRR).
- Common Mistakes / Failure Modes: Running the long run too fast, which leads to excessive fatigue and compromises recovery for other key workouts during the week.

General Aerobic Runs

- Name: General Aerobic Runs
- Plain Definition: Shorter than a long run and performed at a comfortable, conversational pace.
- Purpose: To increase weekly mileage and improve overall aerobic fitness without compromising recovery from more strenuous workouts.
- Typical Use: Constitutes the majority of runs in a training plan, filling the days between harder "quality" sessions.
- Hard Constraints:
  - Pace: Should feel conversational but not like a jog.
  - Intensity: Approximately 70-81% of HRmax or 62-75% of HRR.
  - Effort: Should be greater than a recovery run but less than a long run.
- Common Mistakes / Failure Modes: Running these runs too fast, which turns them into moderately hard efforts and leads to accumulated fatigue, hindering recovery.

Recovery Runs

- Name: Recovery Runs
- Plain Definition: Short, easy runs performed to enhance recovery from harder training sessions.
- Purpose: To improve blood flow to and from the muscles, which brings in nutrients, helps remove waste products, and speeds muscle repair.
- Typical Use: Scheduled the day after a hard workout (e.g., VO₂max intervals, long run) or race.
- Hard Constraints:
  - Pace: The pace should be easy enough to allow for positive adaptations to occur.
  - Primary Goal: To promote adaptation, not to add training stress. This aligns with the "polarized" training principle where easy days must be truly easy to enable hard days to be truly hard.
- Common Mistakes / Failure Modes: Running too fast, which hinders recovery instead of promoting it. This is a common error, especially when running with partners who have different goals for the day.

Lactate Threshold (LT) Training

- Name: Lactate Threshold (LT) Training
- Plain Definition: The exercise intensity just above which the body's lactate production rate exceeds its clearance rate, causing lactate to accumulate in the blood.
- Purpose: To improve LT pace by decreasing lactate production and increasing lactate clearance. Improving LT pace is the single best predictor of race performance for distances from 8K to the half marathon.
- Typical Use: Performed as "tempo runs" (sustained efforts) or "LT intervals" once or twice per week during a race-specific training block.
- Hard Constraints:
  - Pace: LT pace is the exercise intensity just above which lactate begins to accumulate in the blood. This typically corresponds to a pace a well-trained runner can sustain for about 60 minutes.
  - Interval Recovery: For LT intervals, recovery jogs are typically between 20% and 40% of the work interval's duration (e.g., a 2-4 minute jog for an 8-10 minute interval).
- Common Mistakes / Failure Modes: Running LT workouts too fast, which shifts the training stimulus toward the anaerobic system and is less effective for improving lactate threshold.

VO₂max Training

- Name: VO₂max Training
- Plain Definition: A session of repeated high-intensity intervals designed to stress the body's maximum oxygen uptake capacity.
- Purpose: To provide the greatest stimulus for improving maximal aerobic capacity (VO₂max) by increasing the heart's stroke volume and the muscles' ability to extract oxygen from the blood.
- Typical Use: A key weekly workout during race-specific training, particularly for 5K and 10K races.
- Hard Constraints:
  - Pace: Approximately 3K to 5K race pace.
  - Interval Duration: Efforts of 2 to 6 minutes (e.g., 600m to 1600m intervals) are most effective for accumulating time at 95-100% of VO₂max.
  - Interval Recovery: Lightly jog for 50-90% of the time it took to run the preceding interval.
- Common Mistakes / Failure Modes: Running the intervals shorter and faster than prescribed. This shifts the focus to anaerobic training and is less effective at stimulating VO₂max improvements.

Speed Training (and Hill Training)

- Name: Speed Training (and Hill Training)
- Plain Definition: Short, fast repetitions or hill sprints designed to improve basic speed, running form, and power.
- Purpose: To increase stride rate and stride length, improve running technique and economy, and build leg strength that directly transfers to running.
- Typical Use: Incorporated into training plans, often as strides after an easy run or as a dedicated session of short hill repeats.
- Hard Constraints:
  - Strides: Short accelerations lasting 15 to 25 seconds.
  - Power Hills: Uphill efforts should last only 8 to 15 seconds to maintain high intensity and power.
- Common Mistakes / Failure Modes: Straining or tensing up during strides instead of staying relaxed; leaning too far forward when running uphill.

Warm-Up

- Name: Warm-Up
- Plain Definition: A preparatory routine of easy running, stretching, drills, and strides performed before a hard workout or race.
- Purpose: To prepare the cardiovascular and musculoskeletal systems for high-intensity running by increasing heart rate, blood flow, and muscle temperature, thereby reducing injury risk and improving workout performance.
- Typical Use: Always performed before VO₂max, lactate threshold, speed workouts, and races.
- Hard Constraints:
  - Structure: 1) 10-20 mins easy running; 2) 10+ mins of dynamic stretching and drills; 3) A few more minutes of easy running followed by several 100-meter strides.
  - Duration: A pre-race warm-up should take about 45 minutes and be timed to finish about 5 minutes before the start.
- Common Mistakes / Failure Modes: Skipping the warm-up or not performing it thoroughly, which increases injury risk and means the first part of the workout is spent "warming up" rather than training effectively.

Cool-Down

- Name: Cool-Down
- Plain Definition: A post-workout routine of easy running and stretching to help the body return to its pre-exercise state.
- Purpose: To reduce levels of adrenaline, clear lactate from the blood more quickly, and maintain flexibility. It does not prevent delayed-onset muscle soreness (DOMS).
- Typical Use: Performed immediately after all hard workouts (LT, VO₂max, speed) and races.
- Hard Constraints:
  - Structure: 1) 10 to 20 minutes of easy running ("trotting"); 2) Gentle static stretching of major muscle groups.
  - Static Stretch Duration: Stretches should be held for 20 to 30 seconds.
- Common Mistakes / Failure Modes: Stopping abruptly after a hard effort, which can cause blood to pool in the legs and lead to dizziness.

Supplementary Training (Cross-Training)

- Name: Supplementary Training (Cross-Training)
- Plain Definition: Non-running aerobic activities such as water running, swimming, cycling, or using an elliptical trainer.
- Purpose: For healthy runners, it provides extra aerobic work with less impact. For injured runners, it is the primary way to maintain cardiovascular fitness while the body heals.
- Typical Use: Can replace a recovery run for a healthy runner. For an injured runner, it replaces all running workouts, with intensity and duration adjusted to mimic the planned running session.
- Hard Constraints:
  - Intensity: To maintain fitness while injured, intensity must remain high, focusing on interval-based workouts that match the perceived exertion of running workouts.
  - Duration: To replace a recovery run, cycling should be 50-75% longer in duration; water running and elliptical should be about the same duration.
- Common Mistakes / Failure Modes: Not maintaining a high enough intensity (based on perceived exertion) during injury to preserve running fitness.

Supplementary Training (Strength & Plyometrics)

- Name: Supplementary Training (Strength & Plyometrics)
- Plain Definition: Weight training, core exercises, and explosive jumping exercises (plyometrics).
- Purpose: To improve running economy, increase muscle stiffness for better energy return, correct muscle imbalances, and increase injury resilience.
- Typical Use: Strength training 2-3 times per week. Plyometrics no more than twice per week on recovery or general aerobic days.
- Hard Constraints:
  - Scheduling: Avoid weightlifting 24-36 hours before a hard running workout. Perform plyometrics when muscles are not fatigued.
  - Plyometrics Recovery: Rest at least 1 minute between sets due to their high intensity.
- Common Mistakes / Failure Modes: Performing plyometrics with poor form or when fatigued; focusing only on abdominal muscles ("six-pack abs") while neglecting the rest of the core musculature.

Supplementary Training (Flexibility & Drills)

- Name: Supplementary Training (Flexibility & Drills)
- Plain Definition: Dynamic stretching, static stretching, and running form drills.
- Purpose: To improve range of motion, enhance muscle power output (dynamic stretching), lengthen muscle fibers (static stretching), and heighten the efficiency of running form (drills).
- Typical Use: Dynamic stretching is performed before running. Static stretching is performed after running when muscles are warm. Drills are often incorporated after a warm-up and before a quality workout.
- Hard Constraints:
  - Dynamic Stretching: Emphasizes repeatedly moving a joint through its full range of motion. Should take no more than 5 minutes.
  - Static Stretching: Hold each stretch for 20-40 seconds. Perform only when muscles are warm.
- Common Mistakes / Failure Modes: Performing prolonged static stretching before a workout, which may temporarily reduce muscle strength.

3. Decision Rules (IF/THEN)

Pace Selection Logic

- IF workout_type IS "Long Run", THEN pace = CURRENT_10K_PACE \* 1.20 to 1.33.
- IF workout_type IS "VO2max", THEN pace = CURRENT_3K_to_5K_RACE_PACE.
- IF workout_type IS "Lactate Threshold", THEN pace = pace derived from CURRENT_RACE_PERFORMANCE (approximately the pace sustainable in a race lasting 60 minutes).
- IF workout_type IS "General Aerobic", THEN pace = conversational, at an intensity of ~70-81% of HRmax.
- IF workout_type IS "Recovery", THEN pace = very easy, allowing for full recovery and adaptation.

Training Progression and Scaling

- IF increasing_mileage, THEN weekly_increase <= 10%.
- IF increasing_mileage, THEN increase_for_max_2_or_3_weeks, THEN hold_new_mileage_for_at_least_1_week before increasing again.
- IF increasing_mileage, THEN intensity = REDUCED (avoid high-intensity training like VO2max workouts).

Workout Substitution

- IF weather_is_hot_and_humid (e.g., high humidity with temps in 80s/90s F), THEN IF workout_type IS "VO2max" OR "Lactate Threshold", THEN postpone_or_cancel_workout.
- IF runner_is_injured AND feels_pain_at_injury_site, THEN stop_workout_immediately.
- IF runner_is_injured, THEN substitute_running_with_cross_training AND maintain_intensity_via_perceived_exertion.
- IF runner_is_sick (symptoms "below the chest"), THEN stop_training_until_recovered.
- IF runner_is_sick (symptoms "above the chest" e.g., runny nose), THEN proceed_with_caution, consider a recovery run or day off.

Scaling for Special Populations (Masters Runners)

- IF runner_age IN [36, 45], THEN extra_recovery_days_post_VO2max = 1.
- IF runner_age IN [46, 55], THEN extra_recovery_days_post_VO2max = 2.
- IF runner_age IN [56, 65], THEN extra_recovery_days_post_VO2max = 2-3.
- IF runner_age IN [46, 55], THEN extra_recovery_days_post_Tempo_or_LongRun = 1.
- IF runner_age IN [40, 49] AND race_distance IS "5K", THEN min_recovery_days_before_next_hard_workout = 5.
- IF runner_age IN [50, 59] AND race_distance IS "8K-10K", THEN min_recovery_days_before_next_hard_workout = 7.
- IF runner_age IN [60, 69] AND race_distance IS "15K-Half Marathon", THEN min_recovery_days_before_next_hard_workout = 10.
- IF runner_is_master, THEN increase_taper_duration by several days (e.g., a 17-day taper for a goal race instead of a 14-day one).

4. Workout Constructors

Endurance (Long Run) Constructor

- Inputs: GOAL_RACE_DISTANCE, CURRENT_10K_PACE, TOTAL_RUN_DURATION
- Step-by-step Template:
  1. Run: [TOTAL_RUN_DURATION] at a pace 20-33% slower than CURRENT_10K_PACE.
  2. Terrain: Incorporate terrain that simulates the goal race course (e.g., hills).
  3. Post-Run: Initiate recovery fueling within 30-60 minutes.
- Guardrails:
  - Do not run so hard that it requires more than one or two days of recovery. The effort should not compromise other key training sessions.
- Variations:
  - Perform on a hilly course, moderately increasing effort on the uphills to build strength and mental toughness.

Lactate Threshold (Intervals) Constructor

- Inputs: CURRENT_LT_PACE, TOTAL_LT_DURATION_TARGET
- Step-by-step Template:
  1. Warm-up: 10-20 min easy run, followed by light stretching and 2-3 strides.
  2. Main Set: [NUMBER_OF_REPS] x [REP_DURATION] minutes @ CURRENT_LT_PACE.
  3. Recovery: [RECOVERY_DURATION] minutes easy jog between reps.
  4. Cool-down: 10-20 min easy run, followed by light stretching.
- Guardrails:
  - Recovery jog should be between 20% and 40% of the work interval's duration (e.g., 2-4 min recovery for an 8-10 min interval).
- Variations:
  - LT Hills: Perform the work intervals on a long, sustained uphill, jogging down for recovery.
  - Change-of-Pace Tempo: Intersperse periods of running slightly faster than LT pace with periods at or slightly slower than LT pace to improve lactate clearance.

VO₂max (Intervals) Constructor

- Inputs: CURRENT_VO2MAX_PACE (i.e., 3K-5K race pace), TOTAL_INTERVAL_DISTANCE_TARGET
- Step-by-step Template:
  1. Warm-up: 10-20 min easy run, followed by dynamic stretching, drills, and 3-6 strides.
  2. Main Set: [NUMBER_OF_REPS] x [REP_DISTANCE] meters @ CURRENT_VO2MAX_PACE.
  3. Recovery: Slow jog for 50-90% of the time it took to complete the preceding interval.
  4. Cool-down: 10-20 min easy run, followed by light stretching.
- Guardrails:
  - Interval duration should be between 2 and 6 minutes.
  - Pace must be controlled; running too fast will engage the anaerobic system excessively and reduce the effectiveness of the workout for improving VO₂max.
- Variations:
  - Perform the workout on a track for precise pacing.
  - Perform on a treadmill to control for weather and grade.

Speed (Strides) Constructor

- Inputs: TOTAL_STRIDE_COUNT
- Step-by-step Template:
  1. Warm-up: Perform after a thorough warm-up or at the end of a general aerobic run.
  2. Main Set: [TOTAL_STRIDE_COUNT] x ~100 meters.
  - Accelerate purposefully for the first 50 meters.
  - Hold full, relaxed speed for 40-50 meters.
  - Gradually decelerate back to a jog.
  3. Recovery: Easy jog back to the start or for the turns of a track.
- Guardrails:
  - Focus on staying relaxed. Do not practice straining or tensing muscles.
  - Focus on one element of good form (e.g., arm drive, posture) during each stride.
- Variations:
  - Perform on a slight, safe downhill (preferably on grass) to train faster leg turnover.

Power (Short Hills) Constructor

- Inputs: TOTAL_REPETITION_COUNT
- Step-by-step Template:
  1. Warm-up: A thorough warm-up is critical to prevent injury.
  2. Main Set: [TOTAL_REPETITION_COUNT] x [8-15 seconds] running powerfully up a moderate hill.
  3. Execution: Use strong arm drive and leg extension. Focus on maintaining high intensity and power.
  4. Recovery: Walk or jog slowly back down the hill.
- Guardrails:
  - Duration must be kept short (8-15 seconds) to ensure maximal power output on every repetition.
  - Be cautious during the first few sessions to avoid muscle strains.
- Variations:
  - Combine with strides on a flat surface for a comprehensive speed and power workout.

5. Week/Season Structure

Training Phases

- 1. Base Training: The foundational phase focused on building a large aerobic base. This phase prioritizes increasing endurance through long runs and gradually increasing weekly mileage. High-intensity training is avoided.
- 2. Race-Specific Training: Follows the base phase. This period introduces and emphasizes workouts targeted at the physiological demands of the goal race distance (e.g., more VO₂max work for a 5K, more LT work for a half marathon).

Planning Logic

- Training plans are structured backward from a specific goal race date. The schedules provide a week-by-week progression of workouts designed to have the runner peak on race day.
- The training cycle progresses from general fitness to race-specific fitness, starting with a large aerobic base before layering on workouts that target the specific physiological demands of the goal race (e.g., VO₂max for 5K, LT for half marathon).

Distribution of Quality Sessions

- Training follows a polarized or hard/easy principle. Hard days (VO₂max intervals, LT runs, long runs) should be hard enough to provide a powerful training stimulus.
- Easy days (recovery runs, general aerobic runs) must be easy enough to allow for positive physiological adaptations to occur.
- Key quality sessions should be separated by one or more easy days to ensure adequate recovery.

Tapering Principles

- Purpose: To shed accumulated fatigue while retaining fitness, ensuring the runner is rested and sharp on race day.
- Volume: Reduce weekly training volume significantly in the 1-2 weeks prior to the race, often by 30-50% in the final week (e.g., some elite athletes reduce by ~20%, but schedules generally call for a sharper drop).
- Intensity: Maintain training intensity during the taper. Race-pace and faster-than-race-pace running should be included, but in sharply reduced volumes.
- Duration for Masters Athletes: Masters runners require longer recovery and should increase the duration of their tapers by several days (e.g., a 10-day taper for a moderate-priority race, a 17-day taper for a goal race).

6. Minimal Examples

- Example 1: Mid-Phase Lactate Threshold Workout
  - // Rationale: Long intervals at LT pace with short recovery are highly effective at improving lactate clearance.
  - Total Time: ~75 mins
    - Warm-up: 15 min easy run, light stretching, 3 x 100m strides.
    - Main Set: 2 x 15 min @ LT_PACE, with 4 min jog recovery between reps.
    - Cool-down: 15 min easy run + static stretching.
- Example 2: Peak-Phase VO₂max Workout
  - // Rationale: 1200m intervals fall within the optimal 2-6 minute duration to accumulate time at VO₂max.
  - Total Time: ~70 mins
    - Warm-up: 15 min easy run, dynamic stretching & drills, 4 x 100m strides.
    - Main Set: 5 x 1200m @ VO2MAX_PACE (i.e., 5K race pace).
    - Recovery: Jog for 75% of the interval completion time between each rep (e.g., if a 1200m rep takes 4:00, jog for 3:00).
    - Cool-down: 15 min easy run + static stretching.
- Example 3: Speed & Power Combination Workout
  - // Rationale: Short hill repeats build power while relaxed strides improve running economy and speed.
  - Total Time: ~50 mins
    - Warm-up: 15 min easy run, dynamic stretching.
    - Main Set 1 (Power): 6 x 12 seconds powerful running up a moderate hill, with full walk/jog recovery down.
    - Recovery: 3 min easy jog on flat ground.
    - Main Set 2 (Speed): 6 x 100m strides on flat ground, focusing on relaxed speed, with jog-back recovery.
    - Cool-down: 10 min easy run.
- Example 4: Change-of-Pace Tempo Run
  - // Rationale: Alternating paces above and at LT improves the body's ability to clear lactate while under stress.
  - Total Time: ~60 mins
    - Warm-up: 15 min easy run, 2 x 100m strides.
    - Main Set: A continuous 21-minute run, alternating:
    - 3 repetitions of (5 min @ LT_PACE followed by 2 min @ 10K_RACE_PACE).
    - Cool-down: 15 min easy run + static stretching.
