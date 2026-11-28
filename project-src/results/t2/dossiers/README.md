# Racebench 2.2 — adjudication dossiers

Blind dossiers (protocol: `project-src/docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2").
Do **not** open `selection.csv`: it records how the triples were chosen and is the only file here that is not blind.

- equivalence rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted
- runs: 31; dossiers: 31; triples to adjudicate: 91
- transcribe each filled form into `project-src/bench/racebench-2.2.yaml`, rejections included

| dossier | triples | lines |
| --- | --- | --- |
| [svp_simple_001_001/D1](dossiers/svp_simple_001_001-D1.md) | 4 | (32, 55, 32); (32, 58, 32); (32, 60, 32); (35, 55, 35) |
| [svp_simple_003_001/D1](dossiers/svp_simple_003_001-D1.md) | 2 | (50, 65, 50); (55, 65, 55) |
| [svp_simple_005_001/D1](dossiers/svp_simple_005_001-D1.md) | 1 | (32, 46, 32) |
| [svp_simple_006_001/D1](dossiers/svp_simple_006_001-D1.md) | 3 | (33, 52, 33); (35, 52, 33); (35, 52, 35) |
| [svp_simple_007_001/D1](dossiers/svp_simple_007_001-D1.md) | 9 | (32, 47, 34); (32, 47, 42); (32, 50, 42); (34, 47, 38); (34, 47, 42); (34, 50, 38); (34, 50, 40); (34, 50, 42); (38, 50, 42) |
| [svp_simple_007_001/D2](dossiers/svp_simple_007_001-D2.md) | 1 | (32, 49, 34) |
| [svp_simple_009_001/D1](dossiers/svp_simple_009_001-D1.md) | 2 | (26, 44, 32); (26, 44, 33) |
| [svp_simple_009_001/D2](dossiers/svp_simple_009_001-D2.md) | 3 | (35, 46, 37); (35, 46, 38); (37, 46, 38) |
| [svp_simple_011_001/D2](dossiers/svp_simple_011_001-D2.md) | 1 | (33, 43, 35) |
| [svp_simple_013_001/D1](dossiers/svp_simple_013_001-D1.md) | 1 | (39, 65, 39) |
| [svp_simple_014_001/D1](dossiers/svp_simple_014_001-D1.md) | 1 | (39, 58, 39) |
| [svp_simple_016_001/D1](dossiers/svp_simple_016_001-D1.md) | 3 | (24, 33, 26); (24, 33, 27); (25, 33, 27) |
| [svp_simple_017_001/D1](dossiers/svp_simple_017_001-D1.md) | 5 | (29, 39, 30); (30, 39, 30); (30, 39, 32); (32, 39, 29); (32, 39, 32) |
| [svp_simple_018_001/D2](dossiers/svp_simple_018_001-D2.md) | 1 | (41, 54, 49) |
| [svp_simple_021_001/D1](dossiers/svp_simple_021_001-D1.md) | 3 | (34, 79, 44); (34, 79, 65); (65, 79, 65) |
| [svp_simple_022_001/D1](dossiers/svp_simple_022_001-D1.md) | 8 | (32, 66, 63); (43, 66, 39); (43, 66, 55); (43, 66, 63); (55, 66, 39); (56, 66, 39); (56, 66, 63); (58, 66, 39) |
| [svp_simple_023_001/D1](dossiers/svp_simple_023_001-D1.md) | 2 | (28, 39, 25); (28, 39, 35) |
| [svp_simple_025_001/D1](dossiers/svp_simple_025_001-D1.md) | 1 | (29, 38, 35) |
| [svp_simple_026_001/D1](dossiers/svp_simple_026_001-D1.md) | 4 | (34, 40, 26); (34, 40, 27); (34, 43, 26); (34, 43, 27) |
| [svp_simple_026_001/D2](dossiers/svp_simple_026_001-D2.md) | 1 | (40, 43, 40) |
| [svp_simple_027_001/D1](dossiers/svp_simple_027_001-D1.md) | 6 | (35, 41, 27); (35, 41, 28); (35, 45, 27); (35, 45, 28); (35, 48, 27); (35, 48, 28) |
| [svp_simple_027_001/D2](dossiers/svp_simple_027_001-D2.md) | 2 | (41, 45, 41); (41, 48, 41) |
| [svp_simple_027_001/D3](dossiers/svp_simple_027_001-D3.md) | 1 | (45, 48, 45) |
| [svp_simple_028_001/D1](dossiers/svp_simple_028_001-D1.md) | 6 | (36, 43, 29); (36, 43, 30); (36, 49, 29); (36, 49, 30); (36, 53, 29); (36, 53, 30) |
| [svp_simple_028_001/D2](dossiers/svp_simple_028_001-D2.md) | 2 | (43, 49, 43); (43, 53, 43) |
| [svp_simple_028_001/D3](dossiers/svp_simple_028_001-D3.md) | 1 | (49, 53, 49) |
| [svp_simple_029_001/D1](dossiers/svp_simple_029_001-D1.md) | 1 | (45, 83, 80) |
| [svp_simple_030_001/D1](dossiers/svp_simple_030_001-D1.md) | 6 | (36, 43, 29); (36, 43, 30); (36, 52, 29); (36, 52, 30); (36, 56, 29); (36, 56, 30) |
| [svp_simple_030_001/D2](dossiers/svp_simple_030_001-D2.md) | 2 | (43, 52, 43); (43, 56, 43) |
| [svp_simple_030_001/D3](dossiers/svp_simple_030_001-D3.md) | 1 | (52, 56, 52) |
| [svp_simple_031_001/D1](dossiers/svp_simple_031_001-D1.md) | 7 | (46, 90, 65); (46, 90, 85); (73, 90, 46); (73, 90, 65); (73, 90, 83); (73, 90, 85); (83, 90, 65) |
