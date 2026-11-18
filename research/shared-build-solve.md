# Shared build solve (ADR-0341)

The default builder used to solve the final map under address-taken scope,
then solve it again under residual dispatch when the first report was open.
Both scopes verify the same source images, CFG and control-flow certificates.
The shared pass records the blockers waived by residual dispatch as it goes.
The address-taken result puts those blockers back and excludes the
residual-only assumptions and site lists. The builder still uses the
address-taken report to decide when to stop looking for additional code.

Competing release executables read the same retained ROM and map, with no
discovery or lowering in the measurement. Each pair produced equal decoded
reports, including blockers, discharged items, assumptions, and residual
and trapped sites. Three paired runs per ROM gave these median times:

| Retained map | Separate calls | Shared call |
| --- | ---: | ---: |
| GoldenEye | 2.799 s | 1.379 s |
| Paper Mario | 6.894 s | 3.464 s |
| Resident Evil 2 | 1.653 s | 0.825 s |

The CLI tests compare both reports on a closed map, a map with an unknown
register jump, and a map with an ordinary blocker. The builder tests assert
one solve call and cover closed, residual, trapped, and refused outcomes.
