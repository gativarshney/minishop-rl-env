# Decisions

- **State**: The state is small and goal-relative to fit in a table. It tracks current screen, whether a popup is blocking, whether buttons are available, relative quantity, and whether cart matches goal.
- **Reward**: +1.0 for a correct checkout, -1.0 for wrong checkout, -0.01 per step to encourage speed.
- **Episode end**: Ends on checkout or max 20 steps.
- **Skipped**: Full extensive training loop due to time constraints.
