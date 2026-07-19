"""Affinity score tags and consolidator ±1 guidance (-10 … +10)."""

from __future__ import annotations

AFFINITY_MIN = -10
AFFINITY_MAX = 10
DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS = 240

# Fixed prompt tags: score -> template with {name}
AFFINITY_TAGS: dict[int, str] = {
    10: "You deeply love {name} (10:MAX)",
    9: "You adore {name} (9)",
    8: "You are very fond of {name} (8)",
    7: "You care a great deal about {name} (7)",
    6: "You like {name} a lot (6)",
    5: "You have warm feelings toward {name} (5)",
    4: "You like {name} (4)",
    3: "You are friendly toward {name} (3)",
    2: "You feel positively toward {name} (2)",
    1: "You are mildly positive toward {name} (1)",
    0: "You don't really have much of an opinion of {name} (0)",
    -1: "You are mildly wary of {name} (-1)",
    -2: "You feel negatively toward {name} (-2)",
    -3: "You dislike {name} (-3)",
    -4: "You actively dislike {name} (-4)",
    -5: "You have cold feelings toward {name} (-5)",
    -6: "You strongly dislike {name} (-6)",
    -7: "You resent {name} (-7)",
    -8: "You despise {name} (-8)",
    -9: "You deeply hate {name} (-9)",
    -10: "You absolutely hate {name} (-10:MIN)",
}

# Per-score guidance: when to emit +1 / -1 during consolidation (window-only).
AFFINITY_PLUS_GUIDANCE: dict[int, str] = {
    10: "(Impossible — already at MAX. Never emit +1.)",
    9: (
        "Exceptional devotion or sacrifice from {name} that clearly steps past "
        "adoration into deep love — rare, unmistakable, and heartfelt. Do not "
        "raise for another pleasant moment."
    ),
    8: (
        "Sustained warmth or a standout act of care/loyalty that deepens fondness "
        "toward adoration — more than “nice this turn.”"
    ),
    7: (
        "Clear evidence of deepening attachment beyond “care a great deal” — "
        "vulnerability shared and honored, protection, long-horizon kindness. "
        "Hard to earn; do not rubber-stamp."
    ),
    6: (
        "Something that elevates “like a lot” into real caring — emotional support "
        "under pressure, standing up for them, intimacy of trust. Casual friendliness "
        "is +0."
    ),
    5: (
        "Clear positive strengthening within the stable band (reliable kindness, "
        "shared success, repair after a small spat that goes well). Still pickier "
        "than -3…+3."
    ),
    4: (
        "Affirming, trust-building moments that deepen liking into warmer regard. "
        "Steady niceness over empty small talk can qualify; one empty compliment "
        "should not."
    ),
    3: (
        "Friendly rapport clearly warming — pleasant cooperation, humor that lands, "
        "small favors. Volatile: lean +1 when the tone is genuinely good."
    ),
    2: "Positive cues, helpfulness, or shared rapport. Easy to award in the feeling-out zone.",
    1: (
        "Any clear good signal — courtesy that softens into real liking, help given, "
        "pleasant engagement."
    ),
    0: (
        "Soft positive first impressions — politeness, helpfulness, rapport opening. "
        "Default toward movement in this band when anything happened."
    ),
    -1: (
        "Reassurance, apology, or kindness that eases wariness. Easy to grant if they "
        "made a genuine soft approach."
    ),
    -2: (
        "Clear attempt to make things better that land (or show {name} in a better light). "
        "Volatile: reward repair attempts."
    ),
    -3: (
        "Meaningful softening — apology that lands, unexpected help, vulnerability. "
        "Still feeling-out volatile: allow recovery into -2/neutralish if they try."
    ),
    -4: (
        "Only something that regains trust enough to step out of active dislike: "
        "sincere amends, cost paid to make things right, loyalty after conflict. "
        "Everyday civility without repair is +0."
    ),
    -5: (
        "Substantial thaw — sustained conciliatory behavior or a costly good deed. "
        "Harder than in -3…+3."
    ),
    -6: (
        "Serious repair progress toward less visceral dislike (clear amends + changed "
        "behavior). Not a polite hello."
    ),
    -7: (
        "Drift back toward strong dislike / coldness when resentment softens (partial "
        "forgiveness, de-escalation). Easier to move toward the settled middle than "
        "toward deeper hate."
    ),
    -8: (
        "Notable reduction in venom — concession, mercy received, or proof they aren't "
        "wholly the enemy. Prefer thawing toward middle over locking at extremes."
    ),
    -9: (
        "Crack in absolute hatred — hesitation, pity, owed debt repaid, evidence they "
        "were wrong about {name}. Bias toward leaving the rail rather than reinforcing "
        "it when ambiguous."
    ),
    -10: (
        "Hard but possible: serious contrary evidence — sacrifice for them, undeniable "
        "moral turn, or forced reevaluation that even hatred can't ignore. Mild civility "
        "is not enough. Prefer +0 unless thaw is unmistakable."
    ),
}

AFFINITY_MINUS_GUIDANCE: dict[int, str] = {
    10: (
        "Only a serious breach of trust or cruelty from {name} that would genuinely wound "
        "someone deeply in love — betrayal, humiliation, or harm that cannot be laughed "
        "off. Ordinary disagreement, delay, or mild insensitivity is not enough. Prefer "
        "+0 for almost everything else."
    ),
    9: (
        "Clear hurt or disappointment that cools adoration into fondness: broken promise "
        "that mattered, public slight, selfishness where loyalty was expected. Mild "
        "friction stays +0."
    ),
    8: (
        "Meaningful letdown or coldness relative to how fond they are; enough to step "
        "back from “very fond,” not just a blunt word. Drift toward the stable positive "
        "band is easier than climbing. Prefer -1 over clinging high when the window "
        "shows real chill."
    ),
    7: (
        "Noticeable cracks in care (neglect, sharp conflict, taking them for granted). "
        "Easier to fall toward +6/+5 than to climb. Use -1 when the relationship feels "
        "less soft than “care a great deal.”"
    ),
    6: (
        "Solid disappointment or rough treatment — enough that “like a lot” no longer "
        "fits. Petty annoyance alone is not enough (stable band), but bigger failure of "
        "friendship is."
    ),
    5: (
        "Real friction that cools warmth — not routine disagreement. Need something that "
        "feels personally off, not merely inconvenient."
    ),
    4: (
        "Something rough that would make “I like them” feel wrong — betrayal of a fair "
        "expectation, mean-spiritedness, or trust damage. Mere disagreement or doing "
        "something they don't prefer is not enough to leave +4 toward +3."
    ),
    3: (
        "Snubs, rudeness, or awkward friction that make “friendly” feel overstated. "
        "Volatile: lean -1 when vibes sour even modestly."
    ),
    2: "Coldness, pushback, or small harms. Easy to award; first impressions shift quickly.",
    1: (
        "Any clear bad signal — dismissiveness, hassle, or sour tone. Feeling-out: don't "
        "sit on +0 if something happened."
    ),
    0: (
        "Soft negative first impressions — curtness, inconvenience caused, mild distrust. "
        "Same volatility."
    ),
    -1: ("Further grounds for caution — odd behavior, pressure, broken small trust. Volatile."),
    -2: "More friction, confirmation of dislike. Volatile: stack negative signals readily.",
    -3: (
        "Behavior that digs the dislike in — insults, selfishness, threats. Easy to deepen "
        "within this zone."
    ),
    -4: (
        "Further confirmation of active dislike — hostility, deceit, harm. Stable negative "
        "band: need real signals, not minor annoyance alone."
    ),
    -5: "Acts that justify colder distance or sharper dislike. Don't tick for trivia.",
    -6: (
        "Escalation that deepens strong dislike toward resentment. Prefer stability unless "
        "the window is clearly worse (or better)."
    ),
    -7: (
        "Fresh grievances that intensify resentment toward despising them. Harder to push "
        "down than to ease up; require clear new harm or poison."
    ),
    -8: (
        "Atrocity-level or deeply personal worsening that approaches deep hate. Rare; do "
        "not deepen casually."
    ),
    -9: (
        "Only conduct that justifies absolute hatred (-10): profound cruelty or "
        "confirmation of irredeemable enmity. Extremely high bar."
    ),
    -10: "(Impossible — already at MIN. Never emit -1.)",
}


def clamp_affinity(score: int) -> int:
    return max(AFFINITY_MIN, min(AFFINITY_MAX, int(score)))


def format_affinity_tag(score: int, name: str) -> str:
    score = clamp_affinity(score)
    template = AFFINITY_TAGS[score]
    return template.format(name=name)


def plus_guidance(score: int, name: str) -> str:
    score = clamp_affinity(score)
    return AFFINITY_PLUS_GUIDANCE[score].format(name=name)


def minus_guidance(score: int, name: str) -> str:
    score = clamp_affinity(score)
    return AFFINITY_MINUS_GUIDANCE[score].format(name=name)
