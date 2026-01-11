Daniels' Running Formula — distilled reference for an AI coach

0. Core Philosophy

The entire coaching architecture is governed by a core training philosophy. This philosophy provides a consistent framework for all training decisions, ensuring that every prescribed workout is productive, sustainable, and systematically minimizes the risk of injury. It is the guiding intelligence that transforms a collection of workouts into a coherent, effective, and individualized training journey.

The Daniels' methodology is built upon a set of actionable principles that serve as the primary directives for plan generation and adaptation.

- Maximize Benefit, Minimize Stress: Strive to achieve the greatest possible physiological benefit from the least stressful training possible. Avoid the assumption that harder training always yields better results.
- Prioritize Consistency: The single most important factor for success is consistent training. This principle values sustained effort over heroic, isolated workouts.
- Individualize Everything: Every runner has specific abilities, strengths, and weaknesses. Training must be tailored to the individual, not a one-size-fits-all template.
- Train at Current Fitness: All training intensities must be based on a runner's current fitness level, as determined by recent race performances, not on ambitious future goals.
- Embrace Flexibility: Be prepared to adapt the training plan for unexpected factors like adverse weather or a runner's personal schedule. A swapped or modified workout is better than a missed or compromised one.
- Ensure Training is Rewarding: While not always "fun," every workout must have a clear purpose. Understanding this purpose makes the effort rewarding and fosters long-term motivation.
- Progress Stress Conservatively: Increase training stress gradually. A new level of stress should be maintained for at least 3-4 weeks to allow for full physiological adaptation before another increase.
- Prioritize Health and Safety: Never allow a runner to train when sick or injured. Doing so invites a more prolonged setback. Chronic health issues require professional medical evaluation.
- Focus on the Process: Guide the runner to concentrate on the task at hand—executing the current workout or race plan—rather than dwelling on past performances or worrying about distant outcomes.
- Treat Rest as Training: Proper rest, sleep, and nutrition are integral components of the training process, not separate from it. They are essential for recovery and adaptation.
- Reinforce Success: A great race or workout is never a fluke; it is the result of effective training. Use these moments to build confidence and validate the process.

Applying this philosophy with precision requires a deep understanding of the individual athlete, which begins with the systematic collection of a comprehensive runner profile.

1. Runner Profile Inputs (data the AI coach should collect)

The system's initial state requires the ingestion of a comprehensive runner profile. This data is essential for individualizing training loads, setting correct workout intensities based on current fitness, and implementing the safety protocols that are central to the philosophy. Without this foundational information, any training plan is generic and potentially unsafe.

Required

These data points are essential for the initial creation of a valid and safe training plan.

- Recent Race Performance: The distance and finish time of a race completed within the last 4-6 weeks. This is the primary input for determining the runner's VDOT, the foundation of all training-intensity calculations.
- Current Average Weekly Volume: The average number of miles or kilometers the runner has been consistently running per week. This dictates the volume of all workouts.
- Primary Goal Race Distance: The specific event the runner is training for (e.g., 5K, Marathon), which determines the seasonal structure and workout emphasis.

Optional

These supplementary data points allow for deeper personalization and plan adaptation.

- Access to Facilities: Availability of a track, treadmill, or suitable hills for specific workouts.
- Time Availability: The number of days per week and maximum time per session the runner can commit to training.
- Running Experience: The total number of years the runner has been training consistently.
- Subjective Strengths/Weaknesses: The runner's self-assessment of their abilities (e.g., stronger in speed vs. endurance).
- Past Injuries: A history of previous running-related injuries.

Red Flags / Safety Triggers

These inputs must trigger an immediate safety protocol, such as pausing a plan or advising professional medical consultation.

- Current Illness or Injury: The system must enforce the rule: Do not train when sick or injured.
- Chronic Health Issues: Any reported chronic health conditions should trigger a recommendation to seek professional medical clearance before starting or continuing a program.
- Feeling Consistently Below Par: A sustained feeling of being "out of sorts" should prompt a recommendation for medical attention.
- Adverse Environmental Conditions: Any report of extreme heat, cold, or humidity should trigger a warning and potential workout modification (e.g., advising treadmill use or rescheduling).

Once this data is collected, it must be interpreted and applied using a standard set of terms and concepts, ensuring both the coach and the runner speak the same language.

2. Canonical Vocabulary + Ontology

The system operates on a canonical vocabulary of precisely defined training intensities and concepts. This ensures the AI coach can consistently apply the correct training stress and clearly communicate the purpose of each workout. These definitions are the building blocks of the entire training system, linking the runner's profile to specific physiological adaptations.

VDOT

- Name: VDOT
- Plain Definition: A measure of a runner's current fitness level, derived from a recent race performance. It is a "pseudo VO2max" value used to set all training paces.
- Purpose: To establish appropriate and individualized training intensities across all workout types.
- Typical Use: Determined by looking up a recent race time in the VDOT tables (e.g., Table 5.1). This VDOT value is then used to find corresponding paces in the Training Intensities table (e.g., Table 5.2).
- Hard Constraints: Must be based on a current race performance. Recalculate only after a new race performance or after 4-6 weeks of consistent training at the current level.
- Common Mistakes: Using a goal race time instead of a current race time to set paces; updating VDOT too frequently without a corresponding improvement in fitness.

E-Pace (Easy)

- Name: Easy Pace
- Physiological Target: Aerobic base development. Promotes cardiovascular health, strengthens muscles and connective tissues, and increases capillary density.
- Purpose: Building a base, recovery, and adding mileage without excessive stress.
- Typical Use: Warm-ups, cool-downs, recovery runs between quality sessions, and Long runs. Should feel conversational.
- Hard Constraints: None specified, but intensity should be low enough for conversation.
- Common Mistakes: Running E-pace runs too fast, which compromises recovery and adds unnecessary stress.

L-Pace (Long)

- Name: Long Run Pace
- Plain Definition: Extended runs performed at E-Pace.
- Physiological Target: Aerobic endurance. Improves mental toughness, capillary and mitochondrial density, and utilization of fat as a fuel source.
- Purpose: To improve endurance and build resistance to fatigue.
- Typical Use: A single, weekly long run.
- Hard Constraints: Long runs should generally not exceed 25-30% of the total weekly mileage. For most runners, a practical cap is 2.5 hours, regardless of mileage, to prevent excessive recovery time.
- Common Mistakes: Running long runs too fast or increasing their distance too quickly.

M-Pace (Marathon)

- Name: Marathon Pace
- Physiological Target: Metabolic efficiency and neuromuscular adaptation. Conditions the body to the specific demands of marathon race pace.
- Purpose: To practice and adapt to the specific pace a runner intends to hold during a marathon.
- Typical Use: Used in long runs or as dedicated segments within a run for marathon training.
- Hard Constraints: Pacing should be based on a realistic marathon goal derived from a recent race of a shorter distance (e.g., a half marathon is better than a mile for prediction).
- Common Mistakes: Setting an overly ambitious M-pace based on a goal time not supported by current fitness.

T-Pace (Threshold)

- Name: Threshold Pace
- Physiological Target: Lactate Threshold. Training at this intensity improves the body's ability to clear blood lactate, pushing the threshold to a faster pace.
- Purpose: To improve endurance and the ability to sustain a "comfortably hard" effort for an extended period.
- Typical Use: Steady tempo runs or repeated "cruise intervals."
- Hard Constraints: Total running at T-pace in a single session must not exceed 10% of weekly mileage. A single, continuous T-pace run should generally not exceed a duration that equates to this mileage cap (often cited as ~20-30 minutes for most runners, but the mileage cap is the primary rule).
- Common Mistakes: Running T-pace workouts too fast, turning them into a race effort rather than a controlled, steady-state effort.

I-Pace (Interval)

- Name: Interval Pace
- Physiological Target: VO2max (Maximal Aerobic Power). Stresses the cardiovascular system to its maximum ability to transport and utilize oxygen.
- Purpose: To stress and improve aerobic power. This intensity is hard.
- Typical Use: Repeated work bouts of 3 to 5 minutes.
- Hard Constraints: Individual work bouts should not exceed 5 minutes. Total volume at I-pace in a session should be the lesser of 10km or 8% of weekly mileage. Recovery jogs should be of equal or slightly less duration than the work bout.
- Common Mistakes: Running intervals significantly faster than the prescribed I-pace. This introduces anaerobic stress without providing additional aerobic (VO2max) benefit, defeating the purpose of the workout (as shown in Figure 4.3).

R-Pace (Repetition)

- Name: Repetition Pace
- Physiological Target: Neuromuscular System and Running Economy. Improves speed and efficiency by training the nervous system and practicing good form at high speeds with full recovery.
- Purpose: To improve speed and running economy by practicing good form while running fast.
- Typical Use: Short, fast repetitions with full recovery.
- Hard Constraints: Individual work bouts should not last longer than 2 minutes. Total volume at R-pace in a session should be the lesser of 5 miles (8km) or 5% of weekly mileage. Recovery must be long enough for near-full recovery (e.g., 2-3 times the duration of the work bout).
- Common Mistakes: Not taking enough recovery, which changes the workout's purpose and compromises form; practicing poor form due to fatigue.

These definitions provide the fundamental building blocks for creating logical rules that govern training prescription and progression.

3. Decision Rules (IF/THEN)

The decision engine operates on a set of conditional rules. These rules translate the runner's profile and the system's canonical vocabulary into specific, logical training prescriptions, automating the application of the Daniels' principles to ensure every action is appropriate and safe.

Pace Selection Logic

IF runner provides a recent race time:
THEN find the race distance and time in Table 5.1 to determine the runner's current VDOT.
THEN use this VDOT in Table 5.2 to set all training paces (E, M, T, I, R).

IF runner has no recent race time but has a recent mile time:
THEN use the mile race pace as the R-pace for 400m repetitions.
THEN apply the "6-Second Rule": calculate I-pace as 6 seconds slower per 400m than R-pace,
and T-pace as 6 seconds slower per 400m than I-pace.
(Note: Adjust to 7-8 seconds for VDOTs in the 40-50 range).

IF runner is a novice with very slow performance:
THEN use Table 5.3 to determine appropriate R, I, T, and M paces based on their Mile or 5k time.

Progression Logic

IF a runner completes 4 to 6 weeks of consistent training at a given VDOT level
AND workouts begin to feel easier:
THEN a new race to recalculate VDOT is warranted.

IF a runner completes a new race and achieves a better time:
THEN recalculate their VDOT based on the new performance and adjust all training paces accordingly.

DO NOT increase the VDOT value used for setting training paces more than once every 3-4 weeks. This ensures physiological adaptation. A new race performance inside this window should be noted, but paces should only be adjusted after the adaptation period.

Workout Substitution & Modification Logic

IF scheduled for a quality workout (e.g., I-pace repeats) but weather is adverse (e.g., high wind):
THEN substitute with a less pace-dependent workout that achieves a similar purpose
(e.g., fartlek or hard hill repeats).
ELSE, swap the quality day with a scheduled E-day and perform the workout on the day with better weather.

IF training at moderate altitude (e.g., 7,000 ft):
THEN keep R-pace the same as sea-level pace but increase recovery time.
THEN expect I-pace and T-pace to be slower than at sea level; focus on effort, not pace.
THEN run E and L runs by feel and normal breathing pattern.

Scaling & Return-to-Running Logic

IF returning from a break of 5 days or fewer:
THEN resume training at 100% of the previous workload and VDOT.

IF returning from a break of 6-28 days:
THEN reduce training load to 50% for the first half of the return period, and 75% for the second half.
THEN adjust VDOT based on Table 9.2 (e.g., ~93-99% of pre-break VDOT).

IF returning from a break of >8 weeks:
THEN follow a structured, multi-week return plan: 3 weeks at 33% load,
3 weeks at 50% load, etc., with mileage caps.
THEN reduce VDOT based on Table 9.2 (e.g., to ~80-92% of pre-break VDOT, depending on cross-training during the break).

These rules are used to assemble specific daily training sessions using standardized templates known as workout constructors.

4. Workout Constructors (Templates)

Daily training sessions are generated by standardized templates, or constructors. These templates combine the defined workout types with the decision rules to generate complete, safe, and effective training sessions, ensuring all critical components like warm-ups, cool-downs, and safety guardrails are included.

Template: T-Pace (Threshold) Workout

- Inputs: E_PACE, T_PACE, WEEKLY_MILEAGE
  - Note: All paces are derived from the runner's current VDOT.
- Step-by-step Template:
  1. Warm-up: 10-15 minutes of running at E_PACE.
  2. Main Set: [X] minutes of continuous running at T_PACE OR [Y] reps of [Z] miles/km at T_PACE with ~1 minute rest between reps.
  3. Cool-down: 10-15 minutes of running at E_PACE.
- Guardrails:
  - Total time/volume at T_PACE must NOT exceed 10% of WEEKLY_MILEAGE.
  - A single, continuous run at T_PACE should NOT exceed a duration equivalent to the 10% mileage cap.
- Variations:
  - Tempo Run: A single, continuous block of T-pace running (e.g., 20 minutes @ T_PACE).
  - Cruise Intervals: Broken intervals (e.g., 3 x 1 mile @ T_PACE w/ 1 min rest).

Template: I-Pace (Interval) Workout

- Inputs: E_PACE, I_PACE, WEEKLY_MILEAGE
  - Note: All paces are derived from the runner's current VDOT.
- Step-by-step Template:
  1. Warm-up: 10-15 minutes of running at E_PACE, followed by 4-6 light strides.
  2. Main Set: [X] reps of [Y] meters/duration at I_PACE, with a recovery jog of [Z] duration.
  3. Cool-down: 10-15 minutes of running at E_PACE.
- Guardrails:
  - Each work bout at I_PACE MUST be between 3 and 5 minutes in duration.
  - Total volume at I_PACE must NOT exceed the lesser of 10km OR 8% of WEEKLY_MILEAGE.
  - Recovery jog duration should be equal to or slightly less than the work bout duration.
- Variations:
  - Treadmill: Use a steep grade (e.g., 4-6%) at a slower speed to elicit the same effort, reducing impact.

Template: R-Pace (Repetition) Workout

- Inputs: E_PACE, R_PACE, WEEKLY_MILEAGE
  - Note: All paces are derived from the runner's current VDOT.
- Step-by-step Template:
  1. Warm-up: 10-15 minutes of running at E_PACE, followed by 4-6 light strides.
  2. Main Set: [X] reps of [Y] meters at R_PACE, with a [Z] meter slow jog for recovery.
  3. Cool-down: 10-15 minutes of running at E_PACE.
- Guardrails:
  - Each work bout at R_PACE must NOT exceed 2 minutes in duration.
  - Total volume at R_PACE must NOT exceed the lesser of 5 miles (8km) OR 5% of WEEKLY_MILEAGE.
  - Recovery must be sufficient for near-full recovery (jog recovery duration should be 2-3x the work bout duration).
- Variations:
  - Hills: Perform reps as uphill runs to build strength. Jog slowly back down for recovery.

These daily workouts are then organized into a logical, long-term progression across a full training season, or macrocycle.

5. Week/Season Structure

The macrocycle, or seasonal plan, is architected to ensure progressive fitness development. A structured season layers different types of training stress in a logical sequence, ensuring the runner builds fitness progressively and arrives at their goal race prepared to perform optimally without being overtrained.

Phases of Training

A training season is divided into four distinct phases, each with a specific goal and a primary type of quality (Q) training.

1. Phase I (Foundation & Injury Prevention): Goal is building base fitness and preparing the body's muscles and connective tissues for harder work. Consists almost exclusively of Easy (E) and Long (L) runs, supplemented with light strides (ST).
2. Phase II (Early Quality): Goal is to introduce faster running to improve speed and economy without imposing major systemic stress. The primary quality (Q) workouts are Repetition (R-Pace) sessions.
3. Phase III (Transition Quality): This is the most demanding phase, designed to maximize aerobic fitness (VO2max). The primary quality (Q) workouts are Interval (I-Pace) sessions.
4. Phase IV (Final Quality): Goal is to sharpen for racing and peak by reducing overall stress while maintaining intensity. Primary Q workouts shift to Threshold (T-Pace) sessions, which provide significant benefit with less stress than I-Pace. For longer-distance specialists, T-Pace is the focus. Shorter-distance specialists should incorporate mixed sessions combining T-Pace and R-Pace work to maintain sharpness.

Planning Principles

The assembly of these phases into a coherent season follows several core architectural principles.

- Plan Backwards: The process begins by identifying the goal race date. Phase IV (the peak phase) is scheduled for the final weeks leading up to the race. Phase I is planned for the beginning of the season. Phases II and III are then used to bridge the gap between the foundation and the peak.
- Introduce One New Stress: When moving from one phase to the next, only one new type of primary training stress is introduced. For example, after Phase I's E-pace running, Phase II adds the new stress of R-pace speed, but not the aerobic stress of I-pace.
- Phase Length: Each phase ideally lasts for 6 weeks. If the total training time is shorter, phases can be compressed. For a 9-week season, for example, the recommendation is to prioritize 3 weeks of Phase I, 3 weeks of Phase II, and 3 weeks of Phase IV, skipping the highly stressful Phase III.
- Weekly Structure: A typical training week consists of 2-3 Quality (Q) sessions and one Long (L) run. The remaining days are filled with Easy (E) runs for recovery and to build weekly volume.

This seasonal structure provides the high-level blueprint for organizing the daily workouts constructed in the previous section.

6. Minimal Examples

The following are minimal, complete examples of instantiated workout constructors. They demonstrate how the templates are populated with specific distances and paces derived from a runner's VDOT, creating a clear, actionable plan for a given day.

- Threshold (T) Example: 15min run @ E_PACE; 4 x 1 mile @ T_PACE w/ 1min jog recovery; 15min run @ E_PACE.
- Interval (I) Example: 15min run @ E_PACE + 4 strides; 5 x 1000m @ I_PACE w/ 800m jog recovery; 15min run @ E_PACE.
- Repetition (R) Example: 15min run @ E_PACE + 4 strides; 10 x 400m @ R_PACE w/ 400m jog recovery; 15min run @ E_PACE.
- Marathon (M) Long Run Example: 3 miles @ E_PACE; 8 miles @ M_PACE; 3 miles @ E_PACE.
- Mixed Session Example (Phase IV): 15min run @ E_PACE; 3 miles @ T_PACE; 10min run @ E_PACE; 4 x 200m @ R_PACE w/ 200m jog recovery; 10min run @ E_PACE.
