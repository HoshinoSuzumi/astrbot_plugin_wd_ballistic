# WARDOGS small-arms ballistics data source

Source: `https://wardogs.tools/zh-hans/ballistics` (game build 499480, page
version 1.0.7, read 2026-09-22).  This is a normalized transcription of the
page's embedded calculator payload.  It covers the calculator's 34 weapons,
the ammunition they use, armour configuration, and the inputs needed to
reproduce its direct-hit damage/STK/TTK results.

`undefined` means the source does not author that value; do not silently turn
it into zero.  Falloff points are `distance_m: damage_multiplier`; interpolate
linearly between adjacent points.

For a lossless, machine-readable export of the complete current payload, run
`python3 tools/export_wardogs_ballistics.py -o wardogs_ballistics_raw.json`.
It retains all upstream fields, including `reference.infantryRules`,
`reference.armorRulesByContext`, complete `roundsByCaliber`, every weapon's
rule/tag objects, groups, labels, role affinity, and the armour objects.

## Local image assets

Run `python3 tools/download_wardogs_assets.py` after refreshing the raw JSON.
It downloads every accessible icon into `assets/wardogs/` using the calculator
page as `Origin` and `Referer`, and writes the source URL → local file mapping
to `data/wardogs_ballistics_assets.json`.  The manifest deliberately records
upstream 404s as `unavailable` rather than silently substituting a wrong icon.

## UI collection audit

The values below were also checked through the calculator UI rather than
inferred solely from the embedded payload.  The selector accepts at most eight
weapons, so selection was cleared and collected in five batches; FMJ, HP and
AP were enabled together for every compatible calibre.

| batch | UI selections | visible table rows |
|---|---|---:|
| 1 | all 8 ARs | 24 |
| 2 | all 4 SMGs + GGX 17, Judge, M1911, GGX 18 | 24 |
| 3 | Deagle, Bow, both LMGs, both shotguns, RPG-7, Verba | 14 |
| 4 | MAAWS, MGL-40, all 5 sniper rifles, SKS | 18 |
| 5 | SVD, BMR-308 | 6 |

Non-default armour options were individually selected in the UI: body levels
1–4 and Ghillie, plus helmet levels 1–4 and Ghillie.  At upper torso, the UI
displayed FMJ damage-reduction factors `0.70`, `0.60`, `0.45`, `0.35` for body
levels 1–4 respectively; at head it displayed the same progression for helmet
levels 1–4.  The table also exposed armour-break information (shots to break
and remaining percentage at target death), which is governed by the raw
`reference.armorRulesByContext` rule objects in the lossless export.

## Calculation model

For a round at range `r`:

```text
base = round.base_damage * pellets_if_any
location = universal[hit_location] * profile[weapon.profile][hit_location]
range = linear_interpolate(weapon.falloff, r)  # no curve => 1.0 in source UI
raw_damage = base * location * weapon_rule_multiplier * range

# The site applies matching damage-system rules in category_order.  Armour
# mitigation is weighed by the ammo penetration/effectiveness value; AP loses
# less damage to a plate, HP loses more.  Preserve the rule/tag fields from
# the upstream payload when exact armour-break simulation is required.
damage = apply_matching_infantry_and_armour_rules(raw_damage, tags)
stk = ceil(target_health / damage)
ttk_s = (stk - 1) / (rpm / 60)  # only when RPM is authored
```

The site displays the factors separately: round → universal×profile location
multiplier → weapon rule → armour rule/reduction → range.  A burst weapon's
TTK is best-case after its first burst because burst length and inter-burst
delay are not authored.

## Ammunition

| Calibre | Base | arms class | available ammo / penetration effectiveness |
|---|---:|---|---|
| 9mm | 22 | Small | FMJ 1.0; AP 0.3; HP 1.5 |
| 45ACP | 30 | Small | FMJ 1.0; AP 0.3; HP 1.5 |
| 45Colt | 45 | Small | FMJ 1.0; AP 0.3; HP 1.5 |
| 50AE | 63 | High | FMJ 1.0; AP 0.3; HP 1.5 |
| 545mm | 26 | Medium | FMJ 1.0; AP 0.3; HP 1.5 |
| 556mm | 28 | Medium | FMJ 1.0; AP 0.3; HP 1.5 |
| 762mm | 42 | High | FMJ 1.0; AP 0.3; HP 1.5 |
| 762x54mm | 55 | High | FMJ 1.0; AP 0.3; HP 1.5 |
| 308Win | 60 | High | FMJ 1.0; AP 0.3; HP 1.5 |
| 50Cal | 107 | Special | FMJ 1.0 |
| Arrow | 77 | High | Arrow 1.0 |
| 12g buckshot | 25 × 8 pellets | Small | Buckshot 1.0 |
| 12g slug | 105 | Small | Slug 1.0 |
| 40mm / 84mm / 93mm / 72mm | 100 / 100 / 110 / 200 | — | FMJ 1.0 |

Global armour effectiveness: FMJ/Tracer `1.0`, HP `1.5`, AP `0.3`.  The
source also has AP-by-arms-class values: High `0.5`, Medium `0.6`, Small
`0.7`, Special `1.0`.

## Armour configurations

| Slot | Tier | reduction | durability | covered locations |
|---|---|---:|---:|---|
| Helmet | 1 | 30% | 80 | Head |
| Helmet | 2 | 40% | 100 | Head |
| Helmet | 3 | 55% | 180 | Head, Neck |
| Helmet | 4 | 65% | 200 | Head, Neck |
| Body | 1 | 30% | 200 | Torso lower/middle/upper |
| Body | 2 | 40% | 220 | Torso lower/middle/upper |
| Body | 3 | 55% | 250 | Torso lower/middle/upper |
| Body | 4 | 65% | 300 | Torso lower/middle/upper, Pelvis, Upper arm |
| Helmet/body | Ghillie | source-defined rule | undefined | no ordinary covered locations |

## Hit-location multipliers

Universal: `Head 1, Neck .75, Torso.Upper 1.1, Torso.Middle 1,
Torso.Lower .95, Pelvis .9, Arm.Upper .6, Arm.Lower .5, Arm.Hand .3,
Leg.Thigh .6, Leg.Calf .5, Leg.Foot .3`.

| Profile | Head/neck | torso upper/mid/lower | pelvis | upper/lower/hand arm | thigh/calf/foot |
|---|---|---|---|---|---|
| AR | 2.35 / 2.35 | 1 / 1 / 1 | 1 | .9 / .9 / .9 | .9 / .9 / .9 |
| SMG | 2.1 / 2.1 | 1.05 / 1.05 / 1.05 | 1.05 | 1.3 / 1.3 / 1.3 | 1.3 / 1.3 / 1.3 |
| Sniper | 3.2 / 3.2 | 1.8 / 1.45 / 1.45 | 1.3 | 1.2 / 1.2 / 1.2 | 1.2 / 1.2 / 1.2 |
| DMR | 2.5 / 2.5 | 1.3 / 1.3 / 1.3 | 1 | 1 / 1 / 1 | 1 / 1 / 1 |
| Pistol | 2.1 / 2.1 | 1.05 / 1.05 / 1.05 | 1.05 | 1.3 / 1.3 / 1.3 | 1.3 / 1.3 / 1.3 |
| LMG | 2.3 / 2.3 | 1.05 / 1.05 / 1.05 | 1 | .9 / .9 / .9 | .9 / .9 / .9 |
| Shotgun | 1.5 / 1.5 | .9 / .9 / .9 | .9 | 1.05 / 1.05 / 1.05 | 1.05 / 1.05 / 1.05 |
| Bow | 2.3 / 2.3 | 1.9 / 1.9 / 1.5 | 1 | .8 / .8 / .8 | .8 / .8 / .8 |
| Launcher | 1.5 / 1.5 | 1 / .6 / .6 | .6 | .8 / .8 / .8 | .8 / .8 / .8 |

## Weapons

Columns: `name — calibre; RPM; effective range; falloff`.

```text
AR: A-91 — 556mm; 700; 300; 0:1,300:1,1200:.2
    Bushmaster M17S — 556mm; 700; 300; 0:1,300:1,1200:.2
    KH-2002 — 556mm; 700; 300; 0:1,300:1,1200:.2
    T-21 — 556mm; 750; 550; 0:1,300:1,1200:.2
    AK74 — 545mm; 650; 500; 0:1,500:1,1200:.2
    Galil — 556mm; 650; 400; 0:1,400:1,1200:.2
    M4 — 556mm; 800; 500; 0:1,500:1,1200:.2
    FAL — 308Win; 650; 800; 0:1,800:1,1200:.2
SMG: AMP-9 — 9mm; 900; undefined; 0:1,100:1,200:.6,1200:.1
     PP-19 Vityaz — 9mm; 800; 200; 0:1,200:1,300:.6,1200:.1
     MP5 — 9mm; 800; 200; 0:1,200:1,300:.6,1200:.1
     Super-45 — 45ACP; 1200; 50; 0:1,50:1,70:.6,1200:.2
Sniper: TD 侦察步枪 — 556mm; 46; 300; 0:1,300:1,1200:.2
        莫辛步枪 — 762x54mm; 46; 500; 0:1,500:1,1200:.4
        SV98 — 762x54mm; 46; 1000; 0:1,1000:1,1500:.4
        MK22 — 308Win; 46; 1000; 0:1,500:1,1000:1,1600:.4
        AMR 50 — 50Cal; 41.5; 2000; 0:1,500:1,2000:1,2500:.4
DMR: SKS — 762mm; 420; 400; 0:1,400:1,1200:.2
     SVD — 762x54mm; 480; 800; 0:1,800:1,1200:.2
     BMR-308 — 308Win; 450; 500; 0:1,500:1,1200:.2
Pistol: GGX 17 — 9mm; undefined; 50; 0:1,50:1,1200:.3
        Judge — 45Colt; 200; 50; no authored curve
        M1911 — 45ACP; 430; 50; 0:1,50:1,1200:.3
        GGX 18 — 9mm; 1200; 50; 0:1,50:1,1200:.3
        Deagle — 50AE; 267; undefined; 0:1,100:1,1200:.2
Bow: 复合弓 — Arrow; 90; undefined; 0:1,100:1,1200:.2
LMG: M249 SAW — 556mm; 850; 700; 0:1,700:1,1200:.2
     PKM — 762x54mm; undefined; 1000; 0:1,1000:1,1500:.2
Shotgun: MP43 — 12g; 900; undefined; 0:1,70:1,1200:.2
         M500 — 12g; 120; 70; 0:1,70:1,1200:.2
Launcher: RPG-7 — 93mm; 100; 300; no authored curve
          9K333 Verba — 72mm; 100; 1000; no authored curve
          MAAWS — 84mm; 100; 400; no authored curve
          MGL-40 — 40mm; 75; 400; no authored curve
```

Weapon tags/rules are all zero-percent in the embedded payload except M1911's
`+30%` weapon rule.  Keep the source tags if importing into a rule engine:
they select target-specific rules even when their displayed amount is zero.

All 12 hit-location radio controls were also selected and read from the table.
For the UI's A-91 / FMJ validation case, the resulting total location factors
were: Head `2.35`, Neck `1.76`, Upper/Mid/Lower torso `1.10/1.00/0.95`, Pelvis
`.90`, Upper arm `.54`, Forearm `.45`, Hand `.27`, Thigh `.54`, Calf `.45`,
and Foot `.27`. These equal the product of the recorded universal and AR
profile multipliers.
