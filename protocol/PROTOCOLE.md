# Protocole pré-spécifié

Version 0.2, 1er novembre 2026, amendée avant toute campagne (section 12). Version 0.1 du 30 octobre 2026. Auteur : Abdelbassette Chenna. Toute modification après le début de la campagne doit être datée et justifiée ici.

## 1. Question

Une PR Zephyr ouverte (122911) veut signaler les variations de latence du noyau sous QEMU en mode icount, où le compteur avance avec les instructions exécutées. Elle tient pour nulle toute variation sous 2 %, à cause des effets d'alignement entre deux binaires. Elle laisse de côté `qemu_cortex_m3`, faute de compteur DWT dans QEMU.

**Question centrale :** sur un vrai microcontrôleur, une variation du nombre d'instructions entre deux commits annonce-t-elle la variation réelle des cycles, en signe et en taille ?

## 2. Questions de recherche et hypothèses

| Id | Question | Hypothèse |
|---|---|---|
| QR1 | Le signe du delta d'instructions est-il celui du delta de cycles ? | H1 : accord d'au moins 85 % sur les variations réelles |
| QR2 | La taille du delta d'instructions classe-t-elle les variations réelles ? | H2 : corrélation de Spearman d'au moins 0,7 |
| QR3 | Que valent les règles à 2 % ? | H3 : fausses alarmes et ratés sous 20 % chacun |
| QR4 | Quelle part du delta réel vient de la seule disposition du code ? | H4 : l'écart dû à la disposition dépasse 2 % sur au moins 20 % des opérations |
| QR5 | Quelles opérations échappent au compte d'instructions ? | H5 : celles dominées par la mémoire et les exceptions divergent le plus |

Note : ces seuils sont fixés avant toute donnée. Une hypothèse réfutée reste un résultat publiable.

## 3. Dispositif

**Cible principale.** nRF52840DK d'IoT-LAB, Cortex-M4 à 64 MHz, dix nœuds à Saclay, Zephyr annoncé par le banc. Cible secondaire si le temps le permet : ST B-L475E-IOT01A (`st-iotnode`).

**Émulateur.** Renode 1.17.0 avec sa plateforme `nrf52840.repl`, complétée par son modèle `Miscellaneous.DWT` à 8 MHz et un processeur réglé à 8 MIPS. Le temps virtuel de Renode avance par pas de 125 ns : ce réglage donne un pas par instruction, ce que la porte P2 contrôle. Ce temps virtuel n'a aucun sens physique ici, seul le compte sert.

**Même binaire.** La même image ELF tourne sur carte et sous Renode. Le firmware lit toujours CYCCNT : cycles sur carte, instructions sous Renode. La lecture est une fonction non inlinée, car une lecture en ligne verrait un compte périmé sous Renode (constat de la section 9). Une comparaison QEMU sur `mps2/an385`, avec une image distincte, reste un contrôle secondaire.

**Firmware.** `fw/` mesure 20 lignes : surcoût du compteur, 2 calibrations et 17 opérations du noyau reprenant les familles de la PR (sémaphore, mutex, yield, FIFO, LIFO, pile, file de messages, événements, variable de condition, tas, thread, entrée et sortie d'interruption). Chaque opération compte 1 000 échantillons, résumés par minimum, déciles, médiane, maximum et moyenne. Le même code de benchmark s'applique à tous les commits, comme le fait la PR. L'interruption mesurée est une vraie ligne NVIC mise en attente, pas `irq_offload`, qui exige le mode test. Le tag de l'image occupe un tableau de taille fixe : `parent` et `child` n'ayant pas la même longueur, `.rodata` varierait sinon sans lien avec le commit.

**Options de build.** Celles du board par défaut, plus `fw/prj.conf`. Pas de mode test (`CONFIG_TEST` active la journalisation et la protection matérielle de pile), pas de userspace, pas de canaris, pas d'assertions. Les paramètres effectifs sont archivés depuis `.config` pour chaque image.

**Facteurs de répétition.**

| Facteur | Niveaux |
|---|---|
| Commit | parent et enfant de chaque paire |
| Disposition | 4 images par commit : bourrage de 0, 4, 8 et 12 octets |
| Placebo | 8 images sur 6 commits : même code, un écart après une fonction du noyau tirée au sort |
| Répétition | 5 tours par démarrage, 3 démarrages par image |
| Nœud | 1 nœud pour toute la campagne, 2 autres sur 10 % des images |

Note : le bourrage placé devant le texte du noyau le décale d'un bloc sans changer ses instructions. Il donne l'enveloppe du décalage rigide, une borne basse du bruit, car il laisse intactes les positions relatives des fonctions. Le pas vaut 4 parce que les fonctions alignées sur 4 octets passent en tête à l'édition de liens.

Note : le placebo imite la signature d'un commit, qui déplace ce qui suit le code modifié. Sa fonction et son écart, pair, de 2 à 16 octets, sont tirés par `campaign/build_placebo.py`. Les rangs impairs coupent dans `arch/arm/core/cortex_m`, en amont du noyau, les rangs pairs dans le noyau, car les fonctions chaudes sont en tête du noyau et une coupure dans le noyau les atteint rarement. Il est obtenu à l'édition de liens, sans recompiler. `campaign/check_placebo.py` compare ses fonctions à celles de l'image d'origine.

Note : les 6 commits à placebos sont les parents des 5 premières paires de la strate A et de la première paire de la strate B.

## 4. Choix des paires

La règle s'applique sans jugement manuel et `campaign/select_pairs.py` l'exécute.

1. Population : commits de premier parent de la branche principale, sans fusion, depuis le tag fixé le jour du gel, touchant `kernel/`, `include/zephyr/kernel*` ou `arch/arm/core/cortex_m/`.
2. Strate A : commits touchant un fichier du chemin chaud (`sched.c`, `sem.c`, `mutex.c`, `thread.c`, `queue.c`, `msg_q.c`, `events.c`, `condvar.c`, `stack.c`, `kheap.c`, `kernel/include/`, fichiers `swap` et `exc_exit` Cortex-M).
3. Strate B : tous les autres.
4. Tirage aléatoire de graine 20261030 : 24 paires en strate A, 6 en strate B.
5. Un commit qui ne compile pas pour la cible est remplacé par le suivant du tirage, et cet échec est compté. Un échec de git ou de `west update` arrête la campagne sans toucher à l'échantillon : seul un échec de compilation compte.

Note : une paire sans effet sur le code compilé reste dans l'échantillon. Elle sert de nul naturel. Tirage d'essai sur `v4.4.0..0534e997eacb` : 327 commits éligibles, 138 en strate A et 189 en strate B. L'intervalle définitif sera gelé au début de la campagne.

**Mutants injectés.** Sur un seul commit gelé, deux familles de 4 mutants dans `z_impl_k_sem_give` : `alu` (N instructions arithmétiques) et `load` (N lectures mémoire), avec N dans 4, 8, 16 et 32. Le delta d'instructions y est connu. Les deux familles donnent le même delta d'instructions ; leurs coûts en cycles devaient différer, or ils sont presque égaux (section 13).

## 5. Analyse

`analysis/delta_metrics.py` implémente cette section.

- **Cellule :** médiane sur les tours de la médiane d'une opération, pour une image et une plateforme.
- **Référence R1, critère principal :** delta des images telles que compilées, sans bourrage, enfant sur parent, moins 1. La carte étant déterministe, ce delta se lit sans test.
- **Référence R2, secondaire :** effet du code, variation de la moyenne des 4 cellules de disposition, enfant sur parent. Une cellule compte comme déplacée si ce delta dépasse le plancher placebo de l'opération.
- **Plancher :** pour une opération, le plus grand de deux écarts relatifs : entre un placebo et son image telle que compilée, et entre les 4 décalages d'un même commit.
- **Règle de l'émulateur :** stable si le delta absolu est sous le seuil, sinon hausse ou baisse selon le signe.

| Critère | Définition | Incertitude |
|---|---|---|
| C1 | Accord de signe sur toutes les cellules où R1 n'est pas nul | Bootstrap par paire |
| C2 | Spearman entre deltas émulateur et R1, sur toutes les cellules | Bootstrap par paire |
| C3 | Fausses alarmes à 2 %, sur R1 puis sur R2 | Bootstrap par paire |
| C4 | Ratés à 2 %, sur R1 puis sur R2 | Bootstrap par paire |
| C5 | Part des opérations dont l'écart de disposition dépasse 2 % | Bootstrap par paire |

Note : les opérations d'une même paire ne sont pas indépendantes, donc le rééchantillonnage se fait par paire, 2 000 tirages, graine 20261030. Le balayage de seuil de 0 à 5 % et l'analyse par famille d'opérations sont exploratoires et seront présentés comme tels.

Une cellule où Renode vaut 0 alors que R1 ne l'est pas compte comme un désaccord pour C1 : elle n'est jamais exclue, et sa part est publiée à côté de C1. C1 et C2 portent sur toutes les cellules, sans filtre, car une référence stricte ne garderait que les gros effets et flatterait l'émulateur. Ces deux critères sont donc plus exigeants que dans la version 0.1. Les seuils de H1 et H2 ne changent pas.

Les 6 paires hors chemin chaud servent de contrôle négatif de R2, les mutants de témoin positif. Ni valeur p ni Benjamini-Hochberg : le seul hasard de cette étude serait celui des dispositions injectées. L'article ne revendique rien sur le pire cas : seules les médianes sont analysées, même si minimum, déciles et maximum restent journalisés.

## 6. Portes du pré-test, décision au plus tard le 13 novembre 2026

`analysis/gate_pretest.py` les évalue sur une image, 5 tours et 3 démarrages. Il refuse un fichier qui mêle plusieurs images.

| Porte | Condition | Si elle échoue |
|---|---|---|
| P0 | Compte IoT-LAB ouvert, flash et série fonctionnels sur nRF52840DK | Emprunter une carte, sinon plan B |
| P1 | `calib.alu` au-dessus de 900 sur carte et sous Renode | Revoir la lecture du compteur |
| P2 | Sous Renode, `calib.alu` et `calib.load` moins le surcoût restent entre 1 000 et 1 010 | Compte d'instructions non fiable, arrêter ce bras |
| P3 | Sur carte, écart des médianes sous 1 % sur au moins 80 % des opérations | Cycles instables, plan B |
| P4 | Rapport cycles sur instructions avec un coefficient de variation d'au moins 5 % | Relation triviale, plan B |

Note : le plan B est le contrat formel des mémoires flash, sur le PC local. Il faut aussi parcourir les sommaires EMSOFT et RTAS 2024 à 2026 : si la mesure y figure déjà, on bascule également.

Trois portes s'y ajoutent, fixées avant toute mesure de placebo ou de mutant 32.

| Porte | Date limite | Condition |
|---|---|---|
| G1 | 3 novembre | Les placebos gardent toutes les fonctions de leur base, en bougent au moins une, et Renode donne les mêmes comptes sur les 20 lignes |
| G2 | 6 novembre | Carte, 2 nœuds : `mut_alu32` et `mut_load32` dépassent le plancher placebo en hausse sur `sem.give` et `sem.wake`, pour R2 |
| G3 | 13 novembre | Essai à blanc de la chaîne complète sur A000 et A001, médianes reproduites, sommaires parcourus |

Note : le plancher de G2 est provisoire, il vient de 8 placebos sur un seul commit. N vaut 32 car c'est la seule taille prévue qui dépasse 2 % sur `sem.wake`, soit 32 instructions pour 1 322 cycles : une référence qui ne verrait pas ce mutant ne servirait à rien au seuil de 2 %. Les paires A000 et A001 ne décident pas G2.

**Repli.** Si G1 ou G2 échoue, l'étude garde R1 et l'enveloppe des 4 bourrages, sans R2, et déclare cette limite : 272 images.

**Plan B.** On y passe si les médianes ne se reproduisent pas à l'essai à blanc, si une porte P0 à P4 échoue sur une nouvelle image, si la même mesure figure dans les sommaires, ou si G3 n'est pas atteinte le 13 novembre.

## 7. Menaces à la validité

- **Une seule famille de cartes.** Les conclusions valent pour un Cortex-M4 avec cache. La cible secondaire réduit ce risque sans le lever.
- **Benchmark jouet.** Des chemins sans contention ne représentent pas une application. C'est le périmètre de la PR, et il sera annoncé ainsi.
- **Validité de Renode.** Seul le compte d'instructions est utilisé, jamais son temps. La porte P2 le contrôle.
- **Transposition à QEMU.** Deux émulateurs fonctionnels doivent exécuter le même chemin sur une même image, mais QEMU n'a pas de nRF52840 : le contrôle `mps2/an385` reste indirect.
- **Interférences.** Les interruptions du tick et le cache touchent quelques échantillons, d'où l'usage des médianes et du dixième centile.
- **Banc partagé.** État des nœuds et température ne sont pas contrôlés. La répétition sur 2 nœuds borne cet effet.
- **Dispositions redondantes.** Deux bourrages distants de 16 octets donnent les mêmes cycles : les 8 dispositions n'en valent que 4 (section 10).
- **Dérive de la PR.** Elle n'est pas fusionnée et peut changer. L'article cite un commit précis.

## 8. Calendrier

| Date | Étape |
|---|---|
| 31 octobre | Compte IoT-LAB, premier flash, portes P0 à P4, deux paires réelles, 8 dispositions : fait, voir section 10 |
| 3 novembre | Porte G1 : passée le 1er novembre, voir section 13 |
| 6 novembre | Porte G2 : passée le 1er novembre, voir section 13 |
| 13 novembre | Porte G3 : passée le 1er novembre avec réserves, voir section 13. Décision : continuer, replier ou plan B |
| 1er au 30 novembre | Campagne complète, lancée le 1er novembre, voir section 14 |
| 1er au 20 décembre | Analyse et rédaction |
| 31 décembre | Soumission possible à *Real-Time Systems*, sinon *Journal of Systems Architecture* |

## 9. Validation faite sous Renode le 31 octobre 2026

Zephyr 4.5.99 (commit 0534e997eacb), Zephyr SDK 1.0.1, GCC 14.3.0, Renode 1.17.0, sans carte.

| Contrôle | Résultat |
|---|---|
| Compte à l'instruction près | `calib.alu` 1007 et `calib.load` 1008 pour un surcoût de 5 : la porte P2 passe |
| Déterminisme | Écart nul de la médiane sur 5 tours, pour 20 opérations et 10 images |
| Bourrage | Noyau décalé de 0, 4, 12 et 28 octets, code identique, compte d'instructions inchangé |
| Mutant `alu` 8 | +8 exact sur `sem.give` et `sem.wake`, 0 sur les 18 autres lignes |
| Mutant `load` 8 | Même résultat : le compte ne voit pas la différence, comme attendu |
| Cache d'instructions | `CONFIG_NRF_ENABLE_ICACHE=y` dans `.config` |

| Portes | P1, P2 et P3 passent sur Renode contre Renode, P4 échoue : le rapport y vaut 1 partout, comme attendu |

Les deux premières paires du tirage d'essai ont aussi été passées sous Renode, sans choix manuel, avec une image par commit.

| Paire | Commit enfant | Lignes modifiées | Variation d'instructions |
|---|---|---|---|
| A000 | `cf6d9d8fa8` | 6 sur 20 | +1,87 % (`sem.wake`) à +80 % (`condvar.signal`) |
| A001 | `414c3cdeaf` | 3 sur 20 | −0,70 % à −0,99 % (`yield.switch`, `thread.spawn`, `sem.wake`) |

Note : entre parent et enfant, le `.config` ne diffère que par le tag. Quatre de ces 9 variations restent sous 2 % alors que le compte change de façon reproductible : seule la carte dira si les cycles suivent.

Note : ces essais valident la chaîne de mesure, pas la question de recherche.

Huit défauts ont été trouvés et corrigés pendant cette validation :

- deux lectures en ligne de CYCCNT renvoyaient la même valeur, car Renode rafraîchit son compte aux frontières de blocs ;
- à 64 MIPS le compteur ne bougeait que par multiples de 8, d'où le réglage à 8 MIPS ;
- le mode test de Zephyr activait la journalisation et d'autres options, d'où son retrait ;
- le bourrage était jeté à l'édition de liens, puis placé derrière le noyau ;
- un incident de git ou de `west update` comptait comme un échec de compilation et aurait exclu la paire ;
- la longueur du tag différait entre parent et enfant, d'où le tableau de taille fixe ;
- rien ne reliait la sortie de `parse_log.py` à `delta_metrics.py`, d'où `label_rows` et une commande dédiée ;
- le fichier Renode des portes mêlait bourrages et mutants, ce que `gate_pretest.py` refuse désormais.

## 10. Pré-test sur carte du 31 octobre 2026

Nœud `nrf52840dk-1` de Saclay. Expérience 457191 : 10 images, journaux dans `results/raw/silicon/`. Expérience 457194 : les 8 dispositions de `smoke` dans une même session, journaux dans `results/raw/silicon/run2/`, table `results/layouts_silicon.csv`.

| Porte | Résultat |
|---|---|
| P0 | Passe : flash et capture série fonctionnent |
| P1 | Passe : `calib.alu` vaut 1 019 sur carte et 1 007 sous Renode |
| P2 | Passe : 1 002 et 1 003 une fois le surcoût de 5 retiré |
| P3 | Passe : écart nul des médianes sur 4 démarrages et 5 tours, pour les 20 lignes |
| P4 | Passe : rapport de 1,90 (`msgq.put_get`) à 3,13 (`irq.enter`), coefficient de variation de 14,1 % |

Note : P4 a été calculée sur l'image `smoke_p0`, pas sur une paire réelle comme le prévoyait le calendrier. L'écart nul de P3 vaut aussi pour les 120 cellules des 6 images de validation. À l'expérience 457194, 1 ligne de journal sur 3 200 s'écarte : `calib.alu` de p8 médiane à 1 022 au lieu de 1 019 sur un seul tour, sans effet sur la cellule.

**Disposition.** Le même code décalé change les cycles, alors que Renode ne voit aucune différence sur les 20 lignes et les 8 bourrages.

| Opération | p0 | p4 | p8 | p12 | Écart |
|---|---|---|---|---|---|
| `msgq.put_get` | 239 | 233 | 233 | 263 | 12,71 % |
| `condvar.signal` | 46 | 46 | 49 | 46 | 6,52 % |
| `irq.enter` | 47 | 50 | 47 | 47 | 6,38 % |
| `lifo.put_get` | 192 | 184 | 187 | 187 | 4,28 % |
| `fifo.put_get` | 179 | 175 | 172 | 175 | 4,00 % |
| `mutex.lock` | 91 | 91 | 94 | 94 | 3,24 % |

Note : sur les 8 bourrages, 9 opérations sur 17 dépassent 2 %, 3 dépassent 5 %, l'écart médian vaut 2,72 %. Ces chiffres portent sur un seul commit et un seul nœud. p0, p4, p12 et p28 redonnent les mêmes médianes aux deux expériences, sur les 20 lignes.

**Dispositions redondantes.** Dans une même session, p4 et p20, p8 et p24, p12 et p28 donnent les mêmes médianes sur les 20 lignes. p0 et p16 coïncident sur 18 lignes et s'écartent d'un cycle à chaque tour sur `sem.wake` (1 322 et 1 323) et `thread.spawn` (1 668 et 1 669). Deux bourrages de classes différentes ne coïncident que sur 7 à 9 lignes. Les 8 dispositions valent donc 4 classes, modulo 16 octets. Cette période est mesurée ; la ligne de cache de 16 octets reste une explication non vérifiée.

**Conséquence sur le test.** La section 5 ne peut pas rester en l'état. `delta_metrics.py` appelle `mannwhitneyu` en mode `exact`, qui ne corrige pas les ex æquo : sur des cellules en double il renvoie 2/12870, soit 0,00016, alors que 4 cellules contre 4 donnent au mieux 2/70, soit 0,029. Avec 510 tests (30 paires, 17 opérations), Benjamini-Hochberg à 5 % n'accepte 0,029 que si 292 tests au moins l'atteignent. Aucun résultat de ce document n'en dépend : ce test n'a tourné que sur données synthétiques.

Le remplacement du facteur et du test est décidé en section 12.

**Mutants.**

| Mutant | `sem.give` | `sem.wake` | Lignes sans instruction ajoutée |
|---|---|---|---|
| `alu` 8 | +8 cycles | +5 cycles | 5 lignes bougent, de −4 à +10 |
| `load` 8 | +9 cycles | +9 cycles | Les 5 mêmes, avec les mêmes valeurs |

Note : Renode donne +8 sur `sem.give` et `sem.wake`, et 0 ailleurs.

**Paires réelles, une disposition par commit, 17 opérations.**

| Paire | Renode au-delà de 2 % | Carte au-delà de 2 % | Les deux | Signes opposés | Instructions égales, cycles différents |
|---|---|---|---|---|---|
| A000 | 5 | 10 | 5 | 0 | 9 |
| A001 | 0 | 1 | 0 | 1 | 3 |

Note : ces chiffres sont descriptifs. Deux paires ne disent rien de la population.

Sur A000, les 6 lignes où les instructions changent gagnent de 2,00 à 2,55 cycles par instruction ajoutée. Sur A001, `msgq.put_get` gagne 6,79 % sans instruction de plus : c'est aussi la ligne la plus sensible à la disposition. `yield.switch` y perd 6 instructions et gagne 12 cycles.

Deux défauts sont apparus sur carte :

- un reset coupe la ligne en cours et lui colle la suivante, ce qui mêlait les démarrages et pouvait faire planter `parse_log.py` : seuls les démarrages arrivés à `BENCH,DONE` comptent désormais ;
- `nc` affiche une erreur une fois par image : un refus de connexion, ou deux fois sur les 8 images de l'expérience 457194 un nom d'hôte inconnu. Une attente de 5 s après le flash ne l'a pas supprimée et a été retirée.

Note : à l'expérience 457191, `smoke_p0` a été capturée sans cette attente, pendant 30 s, et garde 4 démarrages. Les 9 autres images l'ont été avec l'attente, pendant 12 ou 15 s, et gardent 3 démarrages sur 4. À l'expérience 457194, sans attente et pendant 15 s, les 8 images gardent 4 démarrages sur 4.

## 11. Points non vérifiés à ce jour

- La cause de l'erreur de `nc` est inconnue. Une image, `A001_child_p12`, n'a gardé que 2 démarrages sur les 2 nœuds : la campagne doit remesurer toute image sous 3 démarrages complets.
- Deux nœuds ont été mesurés, en trois sessions sur deux jours.
- La spécification Nordic donne un cache de 2 048 octets, mais ni sa ligne ni son associativité. La période de 16 octets reste une mesure sans cause établie. Les compteurs IHIT et IMISS, confirmés par la spécification, permettraient de la tester.
- L'écart d'un cycle entre p0 et p16, le tour isolé de `calib.alu` et l'échec d'un passage de `mut_alu32` sous Renode (log coupé à 84 lignes, repassé sans erreur) restent inexpliqués.
- Le contrôle QEMU sur `mps2/an385` est construit sur `smoke` (section 14), pas encore mesuré sur les paires.
- Le premier échec de `west update` sur A000 (code 128) ne s'est pas reproduit : sa cause exacte reste inconnue.
- Un commit exigeant un autre module que `cmsis`, `cmsis_6` ou `hal_nordic` échouerait à la compilation pour une raison d'outillage : à vérifier sur chaque échec compté.
- L'analyse de la section 5 n'a tourné que sur données synthétiques et sur les 2 paires de l'essai à blanc, toutes deux de la strate A : le contrôle négatif n'a jamais servi.
- Les chiffres de cette section dépendent de cette version de Renode : à reprendre si elle change.
- Les références de Mytkowicz et al. (ASPLOS 2009) et de Curtsinger et Berger (ASPLOS 2013) sont confirmées, mais seuls leurs résumés ont été lus.
- Les sommaires EMSOFT et RTAS 2024 à 2026 ont été parcourus sur les titres, RTAS 2026 à 27 articles sur 29 annoncés. Notes : `research_notes/Gaps de recherche systèmes embarqués/sommaires_emsoft_rtas.md`.
- Les textes intégraux de Chronos (RTAS 2024) et de CMEmu (MSWiM 2025) n'ont pas pu être lus gratuitement. Sur leurs résumés, figures et dépôt, aucun ne compare des deltas entre commits sur un RTOS : Chronos recouvre l'objectif seulement, CMEmu est un voisin. Ce verdict est à confirmer sur les textes. Notes : `research_notes/Gaps de recherche systèmes embarqués/chronos_cmemu.md`.
- La politique IA de la revue visée reste à consulter avant soumission.
- Le nombre de 8 placebos sur 6 commits est proposé sans calcul de puissance.
- La PR vise QEMU et l'étude mesure Renode : conclure sur la PR demandera le pont de la section 14 ou un périmètre déclaré.

## 12. Amendement du 1er novembre 2026

Fait avant toute campagne, après le pré-test de la section 10 et sur l'avis d'un conseil de 5 relecteurs simulés.

**Motif.** Les 8 bourrages ne valent que 4 classes, ce qui rend le test exact de Mann-Whitney invalide (section 10). Le conseil a écarté 8 ordres aléatoires des fonctions, car un commit décale ce qui suit sans permuter les fonctions, et une règle de plages disjointes, qui n'est que le 2/70 du test sous un autre nom.

**Changements.** Une carte déterministe ne laisse pas de bruit à tester : la question devient ce qu'on appelle une variation réelle. Les sections 3, 4 à 6 et 8 portent désormais deux références, R1 et R2, 4 bourrages au lieu de 8, des placebos, les mutants en témoin positif, et les portes G1 à G3. `analysis/delta_metrics.py` ne calcule plus de valeur p.

**Coût estimé.** 240 images de paires, 32 de mutants et 48 placebos, soit 320 images, environ 9 h de compilation et 3 h 28 de carte.

**Corrections faites pendant les portes, avant la campagne.**

- Le tirage des placebos ne couvrait que le noyau : aucun des 8 premiers n'a déplacé `sem.give`, `sem.take`, `mutex.*` ni `condvar.signal`, et leur plancher nul ne mesurait rien. Les rangs impairs coupent désormais en amont du noyau.
- Le plancher ne comptait que les placebos, et restait nul sur `condvar.signal` et `mutex.lock` alors que les 4 décalages les déplacent de 6,52 % et 3,24 %. Il prend désormais le plus grand des deux écarts.
- Le tirage et le plancher ont été changés après une première évaluation de G2, qui passait aussi. Le premier tirage est archivé dans `results/raw/silicon/g2_first_draw/` et `results/elf_first_draw/`.

## 13. Portes G1 à G3 du 1er novembre 2026

Nœuds 1 et 2 de Saclay. Expérience 457214 : 36 images, 23 min. Expérience 457220 : les 4 placebos retirés, 2 min. Journaux dans `results/raw/silicon/g2_n1/` et `g2_n2/`, tables `results/g2_n1_silicon.csv` et `results/g2_n2_silicon.csv`.

**G1 passe.** Réécrire l'ordre naturel à l'édition de liens redonne l'image d'origine au bit près. Les 8 placebos gardent les instructions des 302 fonctions et en déplacent de 144 à 272. Renode donne les mêmes comptes sur les 20 lignes.

**G2 passe sur les 2 nœuds.**

| Mutant | `sem.give` | `sem.wake` | Plancher de `sem.give` | Plancher de `sem.wake` |
|---|---|---|---|---|
| `mut_alu32` | +66,67 % | +2,97 % | 0 % | 1,28 % |
| `mut_load32` | +68,75 % | +3,27 % | 0 % | 1,28 % |

Note : Renode donne +32 sur ces 2 lignes pour les 2 mutants, et 0 ailleurs. La carte donne +32 et +33 sur `sem.give` à chaque décalage, de +38 à +41 et de +42 à +45 sur `sem.wake`. Les familles `alu` et `load` ne se séparent donc que d'un cycle sur `sem.give` : la famille `load` ne joue pas le rôle prévu.

Note : le plancher vient de 8 placebos sur un seul commit, sans 8 tirages indépendants : g3, g5 et g7 décalent le bloc chaud de 4 octets et donnent des lignes presque égales, comme g6 et g8. Le plancher dépasse 2 % sur 10 opérations sur 17 et 5 % sur 3, médiane 2,74 %.

**G3 passe, avec réserves.** La chaîne va du commit aux critères sur A000 et A001. Les médianes se reproduisent : 720 cellules sur 720 identiques entre les 2 nœuds, 160 sur 160 identiques avec le 31 octobre. Il s'agit bien de 2 cartes, car leurs maxima diffèrent sur 942 lignes de journal sur 14 100. Réserves : `A001_child_p12` a 2 démarrages, le contrôle négatif n'a pas pu servir, et les sommaires ne sont lus que sur les titres (section 11).

Note : sur `A000:parent` p12, `sem.give` et `sem.take` valent 58 et 51 au premier tour de chaque démarrage, 55 et 54 ensuite, sur les 2 nœuds. L'effet est reproductible et absent des autres images. Sa cause est inconnue.

**Essai à blanc, 34 cellules.** Ces chiffres valident la chaîne. Ils ne disent rien de la population.

| Mesure | Valeur |
|---|---|
| Cellules où R1 dépasse 2 % | 11 |
| Parmi elles, ratées par Renode à 2 % | 6 |
| Fausses alarmes de Renode | 0 |
| Cellules où R2 dépasse le plancher | 8 |
| Cellules où R1 n'est pas nul et Renode vaut 0 | 12 sur 21 |

Note : les 6 ratés sur R1 restent tous sous le plancher pour R2 : `irq.enter`, `irq.round_trip`, `mutex.lock` et `mutex.unlock` sur A000, `msgq.put_get` sur A000 et A001. Sur `msgq.put_get` d'A001, R1 donne +6,79 % et R2 +1,69 %. Sur `yield.switch` d'A001, R1 donne +0,58 %, R2 −0,91 % et Renode −0,70 %.

Sept défauts sont apparus sur ces portes :

- `zephyr_ld_options` écartait en silence l'option d'édition de liens : les 8 premiers placebos étaient l'image d'origine, ce que seul `check_placebo.py` a révélé, l'égalité au bit près ne prouvant alors rien ;
- GNU ld 2.43.1 refuse le mot `SECTIONS` dans un fichier d'ordre ;
- l'adresse de `bench_pad`, section vide, changeait l'image d'identité ;
- `check_placebo.py` lisait un écart de 4 octets comme une instruction `.word` ;
- le tirage des placebos n'atteignait pas le bloc chaud ;
- le plancher pouvait rester sous l'écart mesuré entre décalages ;
- `delta_metrics.py` comptait les 3 lignes de contrôle comme des opérations.

## 14. Gel de la campagne du 1er novembre 2026

Fait avant toute compilation de la campagne et avant toute mesure au-delà d'A000 et A001.

**Échantillon.** L'intervalle reste `v4.4.0..0534e997eacb`. `campaign/select_pairs.py` redonne le tirage d'essai à l'octet près : `results/pairs.csv`, SHA-256 `dccc9f45dd0c6fa3`, 327 commits, 24 paires en strate A et 6 en strate B. A000 et A001 restent dans l'échantillon, car le tirage les désigne. Elles ont servi à l'essai à blanc : C1 à C4 seront donc aussi publiés sans elles.

**Images.** 240 images de paires, 32 de mutants, 48 placebos et les 4 décalages de `smoke`, base des mutants, soit 324 images nRF52840.

**Plancher.** Il se calcule sur les 6 commits à placebos, placebos et décalages compris, et ne bouge plus. L'enveloppe des décalages sur les 60 commits sera publiée à part, comme exploratoire.

**Nœuds.** Toutes les images passent sur le nœud 1. Les nœuds 2 et 3 reçoivent 10 % des images, tirées avec la graine 20261030 par `campaign/make_lists.py`. Si un nœud est indisponible, un autre le remplace et le changement est noté ici. Toute image sous 3 démarrages complets est remesurée.

**Contrôle QEMU.** Une image `mps2/an385` par commit, sans bourrage, soit 60 images, sous QEMU 10.0.2 du SDK, avec `-icount shift=7`. QEMU n'ayant pas de DWT, cette image lit le timer 0 du MPS2, à 25 MHz : une instruction y vaut 3,2 tics, confirmé par `calib.alu` à 3 226 pour 1 006 instructions, surcoût compris. Le processeur est un Cortex-M3 et non un M4F : ce contrôle compare deux émulateurs sur des images distinctes, il ne mesure rien sur carte.

| Critère | Définition | Seuil fixé avant mesure |
|---|---|---|
| Q1 | Accord de la règle à 2 % entre QEMU et Renode, sur toutes les cellules | Au moins 90 % |
| Q2 | Spearman entre deltas QEMU et Renode, sur les cellules où l'un des deux n'est pas nul | Au moins 0,9 |

Note : si Q1 ou Q2 échoue, l'article conclut sur le compte d'instructions de Renode seul et ne transpose rien à QEMU. La carte ne peut pas trancher ce point.

Note : `analysis/qemu_bridge.py` arrondit les tics à l'instruction avant de calculer un delta, car le test de la chaîne sur A000 a montré un tic d'écart de phase sur `mutex.lock` (102 et 103), là où le nombre d'instructions ne change pas.

**Firmware.** `fw/src/main.c` gagne le chemin du timer derrière `CONFIG_BENCH_CMSDK_TIMER`, actif sur `mps2/an385` seulement. Recompilée, `smoke_p0` donne les mêmes octets chargés qu'avant ce changement, et le même `.config` hors cette option. Seules les informations de débogage de l'ELF changent.

**Mutants.** Les deux familles restent prévues telles quelles, avec leur plancher. Leur écart de coût étant presque nul à N = 32, leur lecture devient une pente de cycles par instruction ajoutée, sans hypothèse nouvelle.

**Échecs à la compilation.** Deux échecs ont été vérifiés, comme le demande la section 11, avant toute mesure de campagne.

| Paire | Commit | Cause | Suite |
|---|---|---|---|
| A010 | parent `28f157beaeb` | `z_sched_init` est appelée dans `kernel/init.c` sans être déclarée : vrai défaut du commit | Remplacée par A024, 1 échec compté |
| A023 | parent `b04513ce96c` | `west` passe `WEST_TOPDIR` avec des barres obliques inverses, que ce commit transmet tel quel à une macro CMake : défaut d'hôte Windows, sans lien avec la cible | Reste dans l'échantillon, aucun échec compté |

Note : pour A023, `build_image.py` donne le chemin avec des barres obliques. Le drapeau `-fmacro-prefix-map` obtenu est celui des autres commits, déjà présent dans le cache de capacités de Zephyr. La paire A025, compilée entre-temps, sort sans avoir été mesurée ; ses fichiers sont gardés dans `results/elf_excluded` et `results/elf_qemu_excluded`.

Note : l'échantillon final est `results/pairs_final.csv`, soit 24 paires en strate A, de A000 à A024 sans A010, et 6 en strate B.

**Vérification des placebos.** Les 48 placebos gardent toutes leurs instructions. `check_placebo.py` a d'abord signalé `z_impl_k_busy_wait` dans A003_parent_g2 et `k_event_wait_internal` dans A003_parent_g4 : la comparaison montre que seuls les zéros de l'écart y sont imprimés en `movs r0, r0`, et le script accepte désormais cette écriture.

**Contrôle QEMU, résultat.** Q1 vaut 0,998 sur 510 cellules et Q2 vaut 0,999 sur 23 cellules : le contrôle passe. Q1 est porté par les cellules à zéro des deux côtés. Sur les 23 cellules où un delta existe, la règle à 2 % donne la même réponse 22 fois ; l'écart est `sem.wake` d'A000, à +3,01 % sous QEMU et +1,87 % sous Renode.

**Constat fait avant toute lecture des cartes.** Écrit le 1er novembre 2026, alors que la série sur cartes tourne et qu'aucune cellule de carte n'a été analysée.

| Groupe | Paires | Strate A | Strate B |
|---|---|---|---|
| Code identique, seule l'étiquette du firmware change | 20 | 15 | 5 |
| Code modifié, nombre d'instructions modifié | 7 | 6 | 1 |
| Code modifié, nombre d'instructions inchangé | 3 | 3 | 0 |

Note : le test porte sur les octets chargés de `_p0`, parent contre enfant. Les 6 octets d'écart des paires identiques sont ceux de `parent` et `child` dans l'étiquette. A002, A011 et A015 forment le troisième groupe, A011 ne changeant qu'un octet de code.

Note : le critère de sélection de la strate A voit les fichiers touchés, pas le code compilé pour cette carte. La section 4 prévoyait de telles paires comme nuls naturels, mais pas leur proportion : elles laissent 10 paires utiles sur 30.

Trois lectures sont fixées ici pour ne pas dépendre des mesures :

1. L'analyse gelée reste la lecture principale, sur les 30 paires, sans changement.
2. C1 à C4 sont aussi publiés sur les 10 paires dont le code change, comme lecture secondaire, avec `--without` sur les 20 autres. C2 sur 30 paires compte des centaines d'ex æquo à zéro et ne se lit pas seul.
3. Les 20 paires identiques servent de test de déterminisme : leurs 340 cellules de carte doivent donner un delta nul. Toute cellule non nulle est à expliquer avant de lire le reste.

## 15. Extension de l'échantillon du 1er novembre 2026

Décidée par l'auteur à 19 h 45, heure du PC, alors que la série de la section 14 tournait encore. À cet instant, seule la complétude des journaux de carte avait été contrôlée, et aucune cellule de carte n'avait été calculée. Sans cette extension, l'article reposerait sur les 10 paires utiles de la section 14.

**Règle.** Le tirage gelé de la strate A se poursuit dans l'ordre de `results/pairs.csv`, à partir de A025. Une paire est retenue si la section `text` de ses images `_p0` diffère entre parent et enfant. Le tri s'arrête à 15 paires retenues, ce qui porte la strate A à 24 paires utiles. La strate B ne change pas.

Note : le tri ne regarde que le code compilé, jamais une mesure, ni le nombre d'instructions. Chaque paire examinée est notée dans `results/screening.csv`, pour publier le rendement de la règle.

Note : un commit qui ne compile pas suit la règle de la section 4, avec vérification de l'outillage, et son échec va dans `results/build_failures_ext.csv`.

**Images.** Chaque paire retenue reçoit les 4 décalages par côté, soit 8 images, et une image QEMU par commit. Il y a 120 images nRF et 30 images QEMU de plus, sans placebo : le plancher reste celui de la section 14. Les paires retenues forment `results/pairs_extended.csv`, et `results/pairs_final.csv` ne change pas.

**Lectures.**

| Lecture | Paires | Contenu |
|---|---|---|
| Gelée | 30 | L'échantillon de la section 14, sans changement |
| Paires utiles | 25 | Les 10 paires utiles de la section 14 et les 15 retenues |

Note : une hypothèse H1 à H3 n'est tenue pour confirmée que si elle passe sur les deux lectures. Si elles divergent, l'article le dit et ne la confirme pas. H4 reste lue sur la lecture gelée, car C5 ne dépend pas d'un delta entre commits.

Note : la lecture des paires utiles ne vaut que pour les commits qui changent le code compilé pour cette carte. Elle ne dit rien de la part de ces commits dans l'histoire de Zephyr, que seul le rendement du tri décrit.

**Résultat du tri.** Fini le 2 novembre à 1 h 16, heure du PC, après 61 paires examinées, de A025 à A085.

| Résultat | Paires |
|---|---|
| `text` modifié, paire retenue | 15 |
| `text` identique | 43 |
| Échec à la compilation | 3 |

Note : le rendement est de 15 paires sur 58 compilées, soit 25,9 %. Les 15 paires sont A026, A027, A031, A033, A039, A040, A046, A049, A053, A057, A062, A073, A078, A081 et A085.

Note : les 3 échecs viennent de 2 commits. `bde2ba8901b`, parent d'A060 et enfant d'A065, et `05cbc7c98a7`, parent d'A083, appellent `z_sched_init` dans `kernel/init.c` sans la déclarer, comme le parent d'A010 en section 14. C'est un vrai défaut de ces commits, sans lien avec l'hôte ni les modules. Les 3 paires sont comptées comme échecs et ne sont pas remplacées, le tri continuant simplement dans le tirage.

Note : une coupure de réseau a arrêté le tri vers 20 h 55 le 1er novembre. Aucune paire n'a été comptée à tort, et le script a repris à la paire suivante grâce à `results/screening.csv`.

**Exécution.** `campaign/make_lists.py --pairs-only` donne 120 images et 12 images répétées, avec la même graine, dans `results/lists_ext/`. Renode et QEMU écrivent dans `results/raw/renode_ext/` et `results/raw/qemu_ext/`, à part des journaux gelés. L'expérience 457402, sur les nœuds 1, 2 et 3 de Saclay, utilise le dossier `~/camp2`, dont l'archive a été contrôlée par SHA-256.

## 16. Résultats du 2 novembre 2026

**Mesures de l'extension.** Renode et QEMU ont passé les 120 et 30 images sans échec. L'expérience 457402, sur les nœuds 1, 2 et 3 de Saclay, a démarré à 6 h 36 UTC et a fini sans relance : 120 journaux sur le nœud 1 et 12 sur chacun des nœuds 2 et 3, tous à 4 démarrages complets, avec des en-têtes conformes aux noms. L'archive des journaux a été vérifiée par SHA-256. Journaux dans `results/raw/silicon_ext/`, tables `results/campaign_ext_*.csv`.

**Déterminisme.** Les 1 360 cellules des 20 paires identiques donnent un delta nul aux 4 décalages. Les nœuds 2 et 3 redonnent les cellules du nœud 1 sur 765 cellules, sans aucun écart. Sous Renode, aucun compte ne bouge entre les 4 décalages d'un commit, sur 1 530 cas. Dans une image, 16 cellules sur 7 548 changent d'un tour à l'autre, jamais assez pour changer une médiane : 15 répètent le même premier tour à chaque démarrage, et 1 s'écarte de 3 cycles sur un seul tour.

**Verdicts.**

| Hypothèse | Gelée, 30 paires | Utiles, 25 paires | Verdict |
|---|---|---|---|
| H1, C1 au moins 85 % | 25,3 % [8,8 ; 35,9] | 23,6 % [11,8 ; 34,8] | Réfutée |
| H2, C2 au moins 0,7 | 0,38 [−0,10 ; 0,60] | 0,44 [0,20 ; 0,59] | Réfutée |
| H3 sur R1, fausses alarmes et ratés sous 20 % | 0 % et 63,6 % | 10,3 % et 69,4 % | Réfutée par les ratés |
| H3 sur R2 | 8,3 % et 8,3 % | 31,0 % et 16,7 % | Non confirmée, les lectures divergent |
| H4, C5 au moins 20 % | 64,7 % [58,8 ; 70,6] | | Confirmée |

Note : sans A000 ni A001, les lectures utiles donnent C1 21,8 %, C2 0,42, ratés sur R1 71,6 %, et les verdicts ne changent pas.

Note : sur les 85 cellules qui bougent de 2 % ou plus telles que compilées, 62 (72,9 %) restent sous le plancher en R2. Renode rate 59 de ces 85 cellules, dont 56 à zéro exact, et 56 de ses ratés sont sous le plancher. Trois effets de code au-dessus du plancher ont un compte d'instructions inchangé : `heap.alloc_free` d'A008, `sem.give` et `yield.switch` d'A033. Le contrôle négatif reste à zéro.

Note : H5, exploratoire. La corrélation de rang entre l'erreur médiane de Renode et l'écart de disposition vaut 0,64 sur les opérations, contre 0,44 pour les cycles par instruction. Les opérations les plus ratées sont `msgq.put_get`, `irq.enter`, `irq.round_trip` et `mutex.unlock`.

**Contrôle QEMU sur les 45 paires.** Q1 vaut 0,997 sur 765 cellules et Q2 0,997 sur 53 cellules : le contrôle passe. Les deux écarts sont au seuil : `sem.wake` d'A000 et `stack.push_pop` d'A078.

**Article.** Rédigé à la suite, dans `article/`, à partir de scripts qui recalculent chaque nombre depuis les journaux : `make_fills.py`, `make_figures.py`, `build_paper.py`. Bibliographie vérifiée dans `article/references_verified.md`, le 2 novembre 2026. Deux travaux proches, trouvés tard, sont cités et réduisent la nouveauté revendiquée : El Yaacoub et al. (RTCSA 2023), deltas prédits statiquement contre DWT sur Cortex-M4F, et Hsu et al. (ESEC/FSE 2023), traces QEMU avec un modèle de débit sur processeurs de bureau.
