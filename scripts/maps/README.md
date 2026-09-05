# Mapping generation and validation

Edit `maps_config.py`, `endgame.py`, `boss_rooms.py` or `presentation.py`, then run from the mod root:

```
python scripts/maps/generate_maps.py
python scripts/maps/generate_maps.py --check
python -m unittest discover -s scripts/maps -p test_maps.py -v
```

The generator updates both Excel banks, preserving their different treasure
classes, and emits the matching C++ header into the sibling `d2rl-plugins`
checkout. `--check` compares every generated table, bank copy, localization,
boss DS1 and plugin header without writing. Test recipes default to disabled;
set `TEST_RECIPES` locally when needed, then regenerate before release.

`presentation.py` also generates the HD monster lookup entries for every map-owned monster ID, including Wardens and late-Hell drop variants. The lookup is included in `--check` and the deployment script.

Approved folded-parchment sprites use Roman numerals I–VI at the bottom right. Sources and exact image-generation prompts are in `art/v4/`; `preview.html` displays converted art at inventory sizes. Rebuild using `python scripts/maps/build_sprites.py --source scripts/maps/art/v4 --neutral-matte`. The explicit matte option converts the generated neutral preview background into alpha; transparent inputs need no option. Both 98px and 49px RGBA-v31 sprites are generated. `presentation.py` binds all 30 map codes and supplies a shipped charm ground-model fallback. The deploy script includes these 19 HD artifacts. Legacy inventory artwork remains inherited from the small charm.

The mapping implementation and engine limitations are documented in
`d2rl-plugins/plugins/maps/README.md`. Labyrinth monsters, skills, property rows,
treasure classes and source DS1s are preserved. Six late-Act-5 level populations
use separate entry-drop monster variants; their non-Hell treasure classes stay
unchanged. Mapping combat populations and Wardens have independent rows.

## September 5 test build

- Generator output equality check passed for both banks and all 30 boss rooms.
- Six Python contract tests passed.
- C++ suite passed: 60,000 rolls, all affixes, family exclusions, compiled-layout
  and revision rejection, effect application/restoration, consumed-map and
  town/warden state, visited-level protection, and 128 tooltip capacities.
- Release MSVC DLL build passed without compiler warnings.
- Original monster, skill, state, property, treasure-class and preset rows were
  compared against Git HEAD and preserved in both banks. Original level rows
  were preserved apart from the six intended entry-population substitutions.
- 66 mapping artifacts installed and hash-verified in the local D2R Reimagined
  installation using `d2rl-plugins/scripts/deploy-maps-test.ps1 -Apply`.
- Original installation files, Trangsgender save files and shared stashes are
  backed up under `d2rl-plugins/build/maps-test-backup/20260905-095737`.

**Live testing is incomplete.** Computer-use launch approval timed out, and no
gameplay was performed. The existing loader settings have `monsterNoDamage` and
`manaCheat` enabled; those must be off for a meaningful difficulty benchmark.
The character selected by the user is stored as `Trangsgender.d2s` in the
`ReimaginedThree` save directory. No character data was changed by this task.

Prioritize runtime calibration, penalty/MF state application and expiration,
native auras, Warden placement/drop bundles, and all body/warden return warps.
Frozen Depths uses the shipped NihlS Warden arena pending authored ice-room
assets. Treat the installed files as a test build until these checks pass.

Rare-capable map quality now matches rings and amulets: Magic=1, Rare=1, Normal=0 in both banks. The former Normal=1 setting was incorrect, and subsequently clearing Magic as well also diverged from working misc items. The regression compares these flags against both ring and amulet rows. Generated maps have no inherited charm automagic. Native spawn tests use the observed letter option typ=r, not numeric typ=6. Live creation still needs confirmation.
