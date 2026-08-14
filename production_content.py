#!/usr/bin/env python3
"""Matérialise la production éditoriale validée de 106 exercices diagnostiques."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from bridge_priorities import atomic_write_json
from drill_contracts import load_json


ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "data" / "drill_plan.json"
SOURCE_BATCH_ID = "hep-db1-20260813-0001"
MODEL = "gpt-5.6-sol"
REASONING = "high"


def diagnostic(mechanism_id: str, reasoning_break: str) -> dict[str, str]:
    return {"mechanism_id": mechanism_id, "reasoning_break": reasoning_break}


def lexical(
    prompt: str,
    answer: str,
    application: str,
    distractors: list[tuple[str, str, str]],
) -> dict[str, Any]:
    return {
        "path": ("orthographe_lexicale", "graphie_lexicale_usage", "core"),
        "prompt": prompt,
        "answer": answer,
        "application": application,
        "choices": [answer, *(item[0] for item in distractors)],
        "diagnostics": {
            choice: diagnostic(mechanism, reason)
            for choice, mechanism, reason in distractors
        },
    }


def lequel(
    prompt: str, answer: str, antecedent: str, reconstruction: str,
) -> dict[str, Any]:
    variants = {
        "auquel": [
            ("auxquels", "accord_antecedent_nombre", f"est au pluriel, alors que {antecedent} est singulier."),
            ("au quel", "forme_composee_separee", "sépare à tort la forme soudée issue de à + lequel."),
            ("à lequel", "contraction_absente", "ne réalise pas la contraction obligatoire de à + lequel au masculin singulier."),
        ],
        "à laquelle": [
            ("auquel", "accord_antecedent_genre", f"est masculin, alors que {antecedent} est féminin."),
            ("à la quelle", "forme_composee_separee", "sépare à tort laquelle, qui s’écrit en un seul mot."),
            ("auxquelles", "accord_antecedent_nombre", f"est au pluriel, alors que {antecedent} est singulier."),
        ],
        "auxquels": [
            ("auxquelles", "accord_antecedent_genre", f"est féminin, alors que {antecedent} est masculin."),
            ("auquel", "accord_antecedent_nombre", f"est au singulier, alors que {antecedent} est pluriel."),
            ("aux quels", "forme_composee_separee", "sépare à tort la forme contractée auxquels."),
        ],
        "auxquelles": [
            ("auxquels", "accord_antecedent_genre", f"est masculin, alors que {antecedent} est féminin."),
            ("à lesquelles", "contraction_absente", "ne réalise pas la contraction requise au pluriel après la préposition à."),
            ("aux quelles", "forme_composee_separee", "sépare à tort la forme contractée auxquelles."),
        ],
    }
    distractors = variants[answer]
    return {
        "path": ("pronoms_relatifs", "regime_a_auquel", "core"),
        "prompt": prompt,
        "answer": answer,
        "application": f"{reconstruction} : la forme attendue est {answer}, accordée avec l’antécédent « {antecedent} ».",
        "choices": [answer, *(item[0] for item in distractors)],
        "diagnostics": {
            choice: diagnostic(mechanism, reason)
            for choice, mechanism, reason in distractors
        },
    }


def dont(prompt: str, relation: str, antecedent: str) -> dict[str, Any]:
    return {
        "path": ("pronoms_relatifs", "possession_dont", "core"),
        "prompt": prompt,
        "answer": "dont",
        "application": f"{relation} : dont reprend ce complément en de et relie les deux propositions.",
        "choices": ["dont", "donc", "d’on", "don"],
        "diagnostics": {
            "donc": diagnostic("confusion_dont_connecteur", f"exprime une conséquence et ne reprend pas le complément {antecedent}."),
            "d’on": diagnostic("confusion_dont_segmentation", f"correspondrait à de + on et ne peut pas reprendre le groupe « {antecedent} »."),
            "don": diagnostic("confusion_dont_nom", "est un nom commun et non le pronom relatif qui relie les deux propositions."),
        },
    }


def ou_ou(prompt: str, answer: str, application: str, reasoning_break: str) -> dict[str, Any]:
    other = "où" if answer == "ou" else "ou"
    return {
        "path": ("homophones_grammaticaux", "ou_ou", "core"),
        "prompt": prompt,
        "answer": answer,
        "application": application,
        "choices": [answer, other],
        "diagnostics": {
            other: diagnostic("confusion_ou_ou", reasoning_break),
        },
    }


def verbal_adjective(
    prompt: str, answer: str, noun: str, participle: str, wrong_gender: str, wrong_number: str,
) -> dict[str, Any]:
    return {
        "path": ("adjectif_verbal_participe_present", "accord_adjectif_invariabilite_participe", "adjectif"),
        "prompt": prompt,
        "answer": answer,
        "application": f"{answer.capitalize()} qualifie le nom « {noun} » : c’est l’adjectif verbal, dont la graphie propre doit être conservée et qui s’accorde avec ce nom.",
        "choices": [answer, participle, wrong_gender, wrong_number],
        "diagnostics": {
            participle: diagnostic("adjectif_verbal_participe_present", f"emploie la graphie du participe présent alors que le mot qualifie « {noun} »."),
            wrong_gender: diagnostic("adjectif_verbal_accord", f"ne respecte pas le genre du nom « {noun} »."),
            wrong_number: diagnostic("adjectif_verbal_accord", f"ne respecte pas le nombre du nom « {noun} »."),
        },
    }


def present_participle(
    prompt: str, answer: str, action: str, adjective: str, feminine: str, plural: str,
) -> dict[str, Any]:
    return {
        "path": ("adjectif_verbal_participe_present", "accord_adjectif_invariabilite_participe", "participe"),
        "prompt": prompt,
        "answer": answer,
        "application": f"{answer.capitalize()} exprime une action du verbe {action} et conserve un complément verbal : le participe présent garde sa graphie verbale et reste invariable.",
        "choices": [answer, adjective, feminine, plural],
        "diagnostics": {
            adjective: diagnostic("adjectif_verbal_participe_present", "emploie la graphie de l’adjectif verbal alors que la forme exprime une action."),
            feminine: diagnostic("participe_present_accorde", "ajoute un accord féminin au participe présent, qui reste invariable."),
            plural: diagnostic("participe_present_accorde", "ajoute un accord pluriel au participe présent, qui reste invariable."),
        },
    }


def gentile(
    prompt: str, answer: str, detail: str, case_error: str, gender_error: str, number_error: str, noun: str,
) -> dict[str, Any]:
    is_people = detail == "peuple"
    case_mechanism = "majuscule_nom_habitant" if is_people else "majuscule_adjectif_nationalite"
    gender_mechanism = "accord_nom_habitant_genre" if is_people else "accord_adjectif_nationalite_genre"
    number_mechanism = "accord_nom_habitant_nombre" if is_people else "accord_adjectif_nationalite_nombre"
    if is_people:
        application = f"{answer} désigne ici une personne ou un groupe : ce nom d’habitant prend une majuscule et suit les indications de genre et de nombre données par « {noun} »."
        case_reason = "garde une minuscule alors que le mot est ici un nom désignant une personne ou un peuple."
    else:
        application = f"{answer.capitalize()} qualifie le nom « {noun} » : l’adjectif de nationalité garde la minuscule et s’accorde avec ce nom."
        case_reason = f"met une majuscule à un adjectif de nationalité qui qualifie « {noun} »."
    return {
        "path": ("gentiles_majuscules", "nom_peuple_adjectif_langue", detail),
        "prompt": prompt,
        "answer": answer,
        "application": application,
        "choices": [answer, case_error, gender_error, number_error],
        "diagnostics": {
            case_error: diagnostic(case_mechanism, case_reason),
            gender_error: diagnostic(gender_mechanism, f"ne respecte pas le genre indiqué par « {noun} »."),
            number_error: diagnostic(number_mechanism, f"ne respecte pas le nombre indiqué par « {noun} »."),
        },
    }


CONTENT: list[dict[str, Any]] = [
    lexical("La réforme vise à assurer la ___ du financement (pérenne).", "pérennité", "Après « la », le blanc attend le nom pérennité. Ce nom conserve les deux n du radical de pérenne et se termine par -ité, sans e final.", [("pérennitée", "nom_feminin_traite_comme_adjectif", "ajoute un e final comme si le nom féminin devait s’accorder à la manière d’un adjectif."), ("pérenité", "consonne_radical", "omet un n du radical conservé dans le nom pérennité."), ("pérenniter", "confusion_nom_infinitif", "remplace la terminaison du nom -ité par la terminaison verbale -er.")]),
    lexical("Cette décision n’est pas ___ définitive (nécessaire).", "nécessairement", "Le mot modifie l’adjectif définitive : il faut l’adverbe nécessairement, formé sur nécessaire avec la terminaison -ment et les accents du radical.", [("nécéssairement", "accent_lexical", "ajoute un accent aigu sur le second e du radical nécessaire."), ("nécesserement", "formation_adverbe_amment_emment", "reconstruit mal le passage de l’adjectif nécessaire à l’adverbe nécessairement."), ("nécessairemant", "graphie_lexicale_analogie", "écrit la fin de l’adverbe d’après sa prononciation au lieu de conserver le suffixe -ment.")]),
    lexical("Une telle ___ reste très rare dans ce secteur.", "occurrence", "Le nom occurrence s’écrit avec deux c et deux r avant la terminaison -ence.", [("occurence", "consonne_radical", "omet un r dans le radical du nom occurrence."), ("ocurrence", "consonne_radical", "omet un c au début du nom occurrence."), ("occurrance", "graphie_lexicale_analogie", "remplace la terminaison attestée -ence par -ance d’après la prononciation.")]),
    lexical("Le comité se trouve devant un véritable ___.", "dilemme", "Le nom dilemme s’écrit avec un seul l, deux m et la terminaison -emme.", [("dilemne", "consonne_radical", "remplace le second m par un n dans la graphie du nom."), ("dilème", "accent_lexical", "ajoute un accent grave et supprime une consonne du mot dilemme."), ("dillemme", "consonne_radical", "double à tort le l initial du mot dilemme.")]),
    lexical("Un service d’___ sera organisé dès huit heures.", "accueil", "Le nom accueil conserve la suite de lettres -cueil après acc-.", [("acceuil", "graphie_lexicale_analogie", "inverse u et e dans la suite graphique -cueil."), ("aceuil", "consonne_radical", "omet un c au début du nom accueil."), ("acueil", "consonne_radical", "omet le second c sans rétablir la graphie correcte de -cueil.")]),
    lexical("Le poste prévoit une ___ conforme aux responsabilités.", "rémunération", "Le nom rémunération commence par rému- et conserve les accents de sa graphie attestée.", [("rénumération", "consonne_radical", "inverse m et n dans le radical du mot rémunération."), ("remunération", "accent_lexical", "omet l’accent aigu initial du nom rémunération."), ("rémunèration", "accent_lexical", "place un accent grave sur le e de la terminaison -ération.")]),
    lexical("Le ___ de cette application se poursuit.", "développement", "Le nom développement conserve les deux p du verbe développer et prend la terminaison -ement.", [("dévelopement", "consonne_radical", "omet un p du radical de développer."), ("dévelloppement", "consonne_radical", "double à tort le l dans le radical."), ("développemment", "graphie_lexicale_analogie", "reconstruit la fin du nom comme celle d’un adverbe en -emment.")]),
    lexical("La ___ au réseau a été rétablie.", "connexion", "Le nom connexion s’écrit avec x et la terminaison -xion.", [("connection", "graphie_lexicale_analogie", "emploie la graphie anglaise en -ction au lieu de la forme française en -xion."), ("connextion", "consonne_radical", "ajoute un t qui n’appartient pas au nom connexion."), ("connecion", "consonne_radical", "omet le x de la graphie attestée.")]),
    lexical("Son ___ a facilité les négociations.", "professionnalisme", "Professionnalisme se forme sur professionnel et conserve les deux n avant -alisme.", [("professionalisme", "consonne_radical", "omet un n dans le radical de professionnel."), ("professionnallisme", "consonne_radical", "double à tort le l dans la terminaison -alisme."), ("profesionnalisme", "consonne_radical", "omet un s dans le radical profession-.")]),
    lexical("Chaque personne conserve le ___ de refuser.", "privilège", "Le nom privilège s’écrit avec un seul l et un accent grave sur le second e.", [("privilége", "accent_lexical", "emploie un accent aigu à la place de l’accent grave."), ("privillège", "consonne_radical", "double à tort le l du mot privilège."), ("privilègee", "graphie_lexicale_analogie", "ajoute un e final qui n’appartient pas au nom privilège.")]),
    lexical("Les deux enquêtes ont été menées en ___.", "parallèle", "Le nom parallèle s’écrit para- puis -llèle, avec deux l consécutifs et un accent grave.", [("paralèle", "consonne_radical", "omet un l dans le radical de parallèle."), ("paralléle", "accent_lexical", "emploie un accent aigu à la place de l’accent grave."), ("parallèlel", "graphie_lexicale_analogie", "ajoute une consonne finale absente de la graphie du nom.")]),
    lexical("La responsable a répondu avec ___.", "bienveillance", "Le nom bienveillance conserve la suite -veill- et se termine par -ance.", [("bienveillence", "graphie_lexicale_analogie", "remplace la terminaison -ance par -ence d’après la prononciation."), ("bienvaillance", "graphie_lexicale_analogie", "remplace à tort la suite -veil- par -vail-."), ("bienveilance", "consonne_radical", "omet un l dans la suite -veillance.")]),
    lexical("La ___ du système aura lieu vendredi.", "maintenance", "Le nom maintenance se termine par -enance puis -ance, conformément à sa graphie française.", [("maintenence", "graphie_lexicale_analogie", "remplace la terminaison -ance par -ence."), ("maintainance", "graphie_lexicale_analogie", "importe la suite anglaise -tain- dans la graphie française."), ("maintennance", "consonne_radical", "double à tort le n au milieu du mot.")]),
    lexical("La ___ de ces incidents préoccupe la direction.", "récurrence", "Récurrence s’écrit avec deux r et deux c, puis la terminaison -ence.", [("récurence", "consonne_radical", "omet un r dans le radical de récurrence."), ("récurrrence", "consonne_radical", "ajoute un troisième r au radical."), ("récurrance", "graphie_lexicale_analogie", "remplace la terminaison -ence par -ance.")]),
    lexical("Le résumé doit rester ___.", "succinct", "L’adjectif succinct s’écrit avec deux c après su-, puis un c devant le t final.", [("succint", "consonne_radical", "omet le c final de la graphie succinct."), ("sussinct", "consonne_radical", "remplace les deux c après su- par deux s d’après la prononciation."), ("succintt", "graphie_lexicale_analogie", "double le t final tout en omettant le c de -ct.")]),
    lexical("La ___ de son récit a convaincu le jury.", "vraisemblance", "Le nom vraisemblance se forme sur vraisemblable et conserve un seul s entre vrai et semblance.", [("vraissemblance", "consonne_radical", "double à tort le s à la jonction de vrai et semblance."), ("vraisemblence", "graphie_lexicale_analogie", "remplace la terminaison -ance par -ence."), ("vraisemblanse", "consonne_radical", "remplace le c de la terminaison -ance par un s.")]),
    lexical("L’___ de la facture met fin au litige.", "acquittement", "Acquittement se forme sur acquitter et conserve les deux t avant -ement.", [("aquitement", "consonne_radical", "omet le c et un t dans le radical acquitt-."), ("acquitement", "consonne_radical", "omet un t du verbe acquitter."), ("acquittemment", "graphie_lexicale_analogie", "double à tort le m de la terminaison -ement.")]),
    lexical("Le service a fourni un soutien ___.", "exceptionnel", "L’adjectif exceptionnel conserve le c de exception et les deux n de la terminaison -onnel.", [("exceptionel", "consonne_radical", "omet un n dans la terminaison -onnel."), ("exeptionnel", "consonne_radical", "omet le c du radical exception-."), ("excepionnel", "consonne_radical", "omet le t dans le radical exception-. ")]),
    lexical("Les deux dossiers seront examinés ___.", "indépendamment", "L’adverbe indépendamment se forme sur indépendant et prend la terminaison -amment.", [("indépendament", "consonne_radical", "omet un m dans la terminaison adverbiale -amment."), ("indépendemment", "formation_adverbe_amment_emment", "choisit -emment au lieu de -amment malgré la base indépendant."), ("indépendammente", "graphie_lexicale_analogie", "ajoute une marque finale d’accord à un adverbe invariable.")]),
    lexical("Elle a ___ résumé les enjeux.", "intelligemment", "L’adverbe intelligemment se forme sur intelligent et prend la terminaison -emment.", [("intelligement", "consonne_radical", "omet un m dans la terminaison -emment."), ("intelligeamment", "formation_adverbe_amment_emment", "emploie -amment au lieu de -emment après la base intelligent."), ("intelligemmentt", "graphie_lexicale_analogie", "ajoute un t final qui n’appartient pas à l’adverbe.")]),

    ou_ou("Tu peux choisir du thé ___ du café.", "ou", "La phrase propose un choix entre le thé et le café. Le remplacement par « ou bien » fonctionne : on écrit donc ou, sans accent.", "ajoute un accent alors que le mot relie ici deux possibilités et peut être remplacé par « ou bien »."),
    ou_ou("Le dossier peut être envoyé aujourd’hui ___ demain.", "ou", "Aujourd’hui et demain sont deux possibilités. Comme « aujourd’hui ou bien demain » conserve le sens, la conjonction ou s’écrit sans accent.", "traite le mot comme une indication de temps, alors qu’il coordonne deux moments proposés en alternative."),
    ou_ou("Chaque personne choisira une présentation orale ___ un rapport écrit.", "ou", "La phrase met en alternative deux formes de travail. Le test « ou bien » est possible : il faut ou sans accent.", "ajoute l’accent du relatif de lieu ou de temps alors que la phrase exprime un choix entre deux travaux."),
    ou_ou("Voici la salle ___ se tiendra la réunion.", "où", "Le pronom reprend le lieu « la salle » : la réunion se tiendra dans cette salle. On écrit où avec un accent grave.", "supprime l’accent alors que le mot reprend un lieu et signifie « dans laquelle »."),
    ou_ou("Je me souviens du jour ___ nous avons reçu la confirmation.", "où", "Le pronom reprend le moment « le jour » : il signifie « durant lequel ». On écrit où avec un accent grave.", "emploie la conjonction de choix alors que le mot reprend ici un moment précis."),
    ou_ou("L’équipe a atteint le stade ___ une nouvelle décision s’impose.", "où", "Le pronom reprend « le stade », envisagé comme une situation atteinte. Il situe le moment de la progression : on écrit où avec un accent grave.", "supprime l’accent alors que le mot situe l’étape à laquelle une nouvelle décision devient nécessaire."),

    lequel("Le dispositif ___ l’équipe a renoncé sera remplacé en septembre.", "auquel", "dispositif", "L’équipe a renoncé à ce dispositif"),
    lequel("La stratégie ___ la direction adhère exige un suivi régulier.", "à laquelle", "stratégie", "La direction adhère à cette stratégie"),
    lequel("Les critères ___ le dossier doit répondre sont clairement définis.", "auxquels", "critères", "Le dossier doit répondre à ces critères"),
    lequel("Les exigences ___ le produit doit satisfaire ont été renforcées.", "auxquelles", "exigences", "Le produit doit satisfaire à ces exigences"),
    lequel("Le programme ___ plusieurs communes contribuent débutera en janvier.", "auquel", "programme", "Plusieurs communes contribuent à ce programme"),
    lequel("L’initiative ___ le syndicat s’oppose sera soumise au vote.", "à laquelle", "initiative", "Le syndicat s’oppose à cette initiative"),
    lequel("Les engagements ___ les partenaires ont consenti seront publiés.", "auxquels", "engagements", "Les partenaires ont consenti à ces engagements"),
    lequel("Les recommandations ___ l’équipe se conforme figurent en annexe.", "auxquelles", "recommandations", "L’équipe se conforme à ces recommandations"),
    lequel("L’obstacle ___ les négociateurs se heurtent demeure important.", "auquel", "obstacle", "Les négociateurs se heurtent à cet obstacle"),
    lequel("La procédure ___ le service a recours réduit les délais.", "à laquelle", "procédure", "Le service a recours à cette procédure"),
    lequel("Les principes ___ nous nous référons sont inscrits dans la charte.", "auxquels", "principes", "Nous nous référons à ces principes"),
    lequel("Les conditions ___ l’aide est accordée seront réexaminées.", "auxquelles", "conditions", "L’aide est accordée à ces conditions"),
    lequel("Le recours ___ l’avocate a renoncé aurait retardé la procédure.", "auquel", "recours", "L’avocate a renoncé à ce recours"),
    lequel("La solution ___ le groupe est parvenu semble durable.", "à laquelle", "solution", "Le groupe est parvenu à cette solution"),
    lequel("Les changements ___ le personnel doit s’adapter seront progressifs.", "auxquels", "changements", "Le personnel doit s’adapter à ces changements"),
    lequel("Les valeurs ___ l’association demeure fidèle guident ses actions.", "auxquelles", "valeurs", "L’association demeure fidèle à ces valeurs"),
    lequel("Le calendrier ___ tous les partenaires se sont ralliés sera maintenu.", "auquel", "calendrier", "Tous les partenaires se sont ralliés à ce calendrier"),
    lequel("La proposition ___ le comité réfléchit sera précisée demain.", "à laquelle", "proposition", "Le comité réfléchit à cette proposition"),
    lequel("Les projets ___ la fondation participe concernent la formation.", "auxquels", "projets", "La fondation participe à ces projets"),
    lequel("Les fonctions ___ ces spécialistes aspirent exigent une solide expérience.", "auxquelles", "fonctions", "Ces spécialistes aspirent à ces fonctions"),

    dont("Le laboratoire ___ les analyses ont révélé l’anomalie publiera ses résultats.", "Les analyses sont celles du laboratoire", "du laboratoire"),
    dont("Le musée ___ la collection vient d’être restaurée rouvrira lundi.", "La collection est celle du musée", "du musée"),
    dont("L’association ___ les statuts ont été révisés convoquera une assemblée.", "Les statuts sont ceux de l’association", "de l’association"),
    dont("L’autrice ___ le roman a reçu un prix rencontrera le public.", "Le roman est celui de l’autrice", "de l’autrice"),
    dont("La ville ___ l’architecture attire les visiteurs protège son centre historique.", "L’architecture est celle de la ville", "de la ville"),
    dont("L’entreprise ___ les comptes ont été contrôlés publiera son rapport annuel.", "Les comptes sont ceux de l’entreprise", "de l’entreprise"),
    dont("Le projet ___ les objectifs restent ambitieux bénéficie d’un nouveau financement.", "Les objectifs sont ceux du projet", "du projet"),
    dont("La candidate ___ l’expérience a convaincu le jury entrera en fonction lundi.", "L’expérience est celle de la candidate", "de la candidate"),
    dont("Le comité ___ l’avis était attendu s’est prononcé ce matin.", "L’avis est celui du comité", "du comité"),
    dont("L’étude ___ les conclusions font débat sera réévaluée.", "Les conclusions sont celles de l’étude", "de l’étude"),
    dont("Le village ___ les traditions demeurent vivantes organise une fête annuelle.", "Les traditions sont celles du village", "du village"),
    dont("L’école ___ les salles ont été rénovées accueillera davantage d’élèves.", "Les salles sont celles de l’école", "de l’école"),
    dont("La chercheuse ___ l’hypothèse a été confirmée présentera ses données.", "L’hypothèse est celle de la chercheuse", "de la chercheuse"),
    dont("Le traité ___ les clauses restent contestées doit être renégocié.", "Les clauses sont celles du traité", "du traité"),
    dont("La société ___ les employés ont été consultés modifiera son organisation.", "Les employés sont ceux de la société", "de la société"),
    dont("Le roman ___ la fin surprend les lecteurs sera adapté au cinéma.", "La fin est celle du roman", "du roman"),
    dont("Le patient ___ les symptômes persistent sera revu demain.", "Les symptômes sont ceux du patient", "du patient"),
    dont("Le festival ___ le programme vient de paraître débutera en juin.", "Le programme est celui du festival", "du festival"),
    dont("L’espèce ___ l’habitat se réduit fait l’objet d’un suivi.", "L’habitat est celui de l’espèce", "de l’espèce"),
    dont("Le fonds d’archives ___ les documents ont été numérisés est désormais accessible.", "Les documents sont ceux du fonds d’archives", "du fonds d’archives"),

    verbal_adjective("Ces décisions paraissent ___ (provoquer) pour une partie du public.", "provocantes", "décisions", "provoquantes", "provocants", "provocante"),
    verbal_adjective("Ces démarches deviennent ___ (fatiguer) à la longue.", "fatigantes", "démarches", "fatiguantes", "fatigants", "fatigante"),
    verbal_adjective("Les preuves fournies sont ___ (convaincre).", "convaincantes", "preuves", "convainquantes", "convaincants", "convaincante"),
    verbal_adjective("Les attitudes ___ (négliger) seront signalées.", "négligentes", "attitudes", "négligeantes", "négligents", "négligente"),
    verbal_adjective("Les interprétations restent ___ (diverger) sur ce point.", "divergentes", "interprétations", "divergeantes", "divergents", "divergente"),
    verbal_adjective("Les analyses sont ___ (converger) malgré des méthodes différentes.", "convergentes", "analyses", "convergeantes", "convergents", "convergente"),
    verbal_adjective("Ces chercheuses sont devenues ___ (influer) dans leur domaine.", "influentes", "chercheuses", "influantes", "influents", "influente"),
    verbal_adjective("Les versions ___ (précéder) contenaient une erreur.", "précédentes", "versions", "précédantes", "précédents", "précédente"),
    verbal_adjective("Les deux salles sont ___ (communiquer).", "communicantes", "salles", "communiquantes", "communicants", "communicante"),
    verbal_adjective("Ces matières deviennent ___ (adhérer) sous l’effet de la chaleur.", "adhérentes", "matières", "adhérantes", "adhérents", "adhérente"),

    present_participle("Les déléguées, ___ (provoquer) un débat animé, ont prolongé la séance.", "provoquant", "provoquer", "provocant", "provoquante", "provoquants"),
    present_participle("Les participantes, ___ (fatiguer) leurs collègues par ces répétitions, ont abrégé la discussion.", "fatiguant", "fatiguer", "fatigant", "fatiguante", "fatiguants"),
    present_participle("Les expertes, ___ (convaincre) le comité, ont obtenu un financement.", "convainquant", "convaincre", "convaincant", "convainquante", "convainquants"),
    present_participle("Les responsables, ___ (négliger) plusieurs avertissements, ont aggravé la situation.", "négligeant", "négliger", "négligent", "négligeante", "négligeants"),
    present_participle("Les deux itinéraires, ___ (diverger) après le pont, mènent à des vallées différentes.", "divergeant", "diverger", "divergent", "divergeante", "divergeants"),
    present_participle("Les délégations, ___ (converger) vers la place centrale, ont ralenti la circulation.", "convergeant", "converger", "convergent", "convergeante", "convergeants"),
    present_participle("Ces décisions, ___ (influer) sur le calendrier, devront être annoncées rapidement.", "influant", "influer", "influent", "influante", "influants"),
    present_participle("Les personnes ___ (précéder) la délégation ouvriront les portes.", "précédant", "précéder", "précédent", "précédante", "précédants"),
    present_participle("Les équipes, ___ (communiquer) leurs résultats chaque semaine, coordonnent mieux leurs travaux.", "communiquant", "communiquer", "communicant", "communiquante", "communiquants"),
    present_participle("Les membres ___ (adhérer) à la nouvelle charte recevront une confirmation.", "adhérant", "adhérer", "adhérent", "adhérante", "adhérants"),

    gentile("La médecin est une ___ établie à Genève.", "Canadienne", "peuple", "canadienne", "Canadien", "Canadiennes", "le déterminant une"),
    gentile("Des ___ ont participé à la rencontre culturelle.", "Italiens", "peuple", "italiens", "Italiennes", "Italien", "le déterminant des"),
    gentile("Le conférencier est un ___ installé à Lausanne.", "Allemand", "peuple", "allemand", "Allemande", "Allemands", "le déterminant un"),
    gentile("Cette architecte est une ___ qui travaille à Sion.", "Française", "peuple", "française", "Français", "Françaises", "le déterminant une"),
    gentile("Plusieurs ___ exposeront leurs œuvres à Bâle.", "Espagnoles", "peuple", "espagnoles", "Espagnols", "Espagnole", "plusieurs et le féminin"),
    gentile("Ces musiciennes sont des ___ établies en Suisse.", "Portugaises", "peuple", "portugaises", "Portugais", "Portugaise", "le déterminant des et le féminin"),
    gentile("La réalisatrice est une ___ récompensée à Locarno.", "Brésilienne", "peuple", "brésilienne", "Brésilien", "Brésiliennes", "le déterminant une"),
    gentile("Les deux chercheurs sont des ___ invités à Neuchâtel.", "Norvégiens", "peuple", "norvégiens", "Norvégiennes", "Norvégien", "les deux chercheurs"),
    gentile("Le chef d’orchestre est un ___ domicilié à Berne.", "Autrichien", "peuple", "autrichien", "Autrichienne", "Autrichiens", "le déterminant un"),
    gentile("Ces athlètes sont des ___ venues pour la compétition.", "Grecques", "peuple", "grecques", "Grecs", "Grecque", "le déterminant des et le féminin"),

    gentile("La délégation ___ présentera son projet demain.", "canadienne", "adjectif", "Canadienne", "canadien", "canadiennes", "délégation"),
    gentile("Des entreprises ___ participeront au salon.", "italiennes", "adjectif", "Italiennes", "italiens", "italienne", "entreprises"),
    gentile("Un laboratoire ___ coordonne cette étude.", "allemand", "adjectif", "Allemand", "allemande", "allemands", "laboratoire"),
    gentile("Les méthodes ___ ont influencé cette recherche.", "françaises", "adjectif", "Françaises", "français", "française", "méthodes"),
    gentile("Une équipe ___ rejoindra le consortium.", "espagnole", "adjectif", "Espagnole", "espagnol", "espagnoles", "équipe"),
    gentile("La chercheuse ___ dirigera les entretiens.", "portugaise", "adjectif", "Portugaise", "portugais", "portugaises", "chercheuse"),
    gentile("La délégation ___ arrivera vendredi.", "brésilienne", "adjectif", "Brésilienne", "brésilien", "brésiliennes", "délégation"),
    gentile("Des solutions ___ seront comparées aux nôtres.", "norvégiennes", "adjectif", "Norvégiennes", "norvégiens", "norvégienne", "solutions"),
    gentile("Les partenaires ___ financeront le programme.", "autrichiens", "adjectif", "Autrichiens", "autrichiennes", "autrichien", "partenaires"),
    gentile("Une association ___ organise cette rencontre.", "grecque", "adjectif", "Grecque", "grec", "grecques", "association"),
]


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = load_json(PLAN)
    pools: dict[tuple[str, str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for item in CONTENT:
        pools[item["path"]].append(item)
    candidates = {
        "schema_version": "hep-drill-production-candidates/1.0",
        "source_plan_fingerprint": plan["fingerprint"],
        "model": MODEL,
        "reasoning": REASONING,
        "source_batch_id": SOURCE_BATCH_ID,
        "drills": [],
    }
    options = {
        "schema_version": "hep-drill-choice-options/1.0",
        "source_batch_id": SOURCE_BATCH_ID,
        "options": [],
    }
    corrections = {
        "schema_version": "hep-choice-corrections/2.0",
        "source_batch_id": SOURCE_BATCH_ID,
        "corrections": [],
    }
    for batch in plan["batches"]:
        for slot in batch["slots"]:
            path = (slot["family"], slot["mechanism_id"], slot["detail_id"])
            if not pools[path]:
                raise ValueError(f"Contenu manquant pour {path}")
            item = pools[path].popleft()
            drill_id = slot["drill_id"]
            candidates["drills"].append({
                "schema_version": "hep-drill/1.0",
                "id": drill_id,
                "source_batch_id": SOURCE_BATCH_ID,
                "family": path[0],
                "mechanism_id": path[1],
                "detail_id": path[2],
                "tense_id": None,
                "prompt": item["prompt"],
                "accepted_answers": [item["answer"]],
                "display_answer": item["answer"],
                "application_note": item["application"],
                "pedagogy_dict_version": "hep-pedagogy-dict/2.0",
            })
            options["options"].append({"drill_id": drill_id, "choices": item["choices"]})
            corrections["corrections"].append({"drill_id": drill_id, "diagnostics": item["diagnostics"]})
    leftovers = {path: len(items) for path, items in pools.items() if items}
    if leftovers:
        raise ValueError(f"Contenu non planifié: {leftovers}")
    return candidates, options, corrections


def main() -> None:
    candidates, options, corrections = materialize()
    atomic_write_json(ROOT / "data" / "production_candidates.json", candidates)
    atomic_write_json(ROOT / "data" / "production_choice_options.json", options)
    atomic_write_json(ROOT / "data" / "production_choice_corrections.json", corrections)
    print(f"{len(candidates['drills'])} exercices matérialisés avec leurs choix et diagnostics.")


if __name__ == "__main__":
    main()
