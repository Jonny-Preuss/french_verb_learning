import pandas as pd
import mlconjug3
from collections.abc import Mapping
from collections import defaultdict

# Load your Excel verb list
df = pd.read_excel("Top_1000_verbs_French_empty.xlsx", sheet_name="Top1000")
verbs = df["French"].dropna().unique()

# Conjugator
conjugator = mlconjug3.Conjugator(language='fr')

# Standard subject order
pronoun_order = ['je', 'tu', 'il (elle, on)', 'nous', 'vous', 'ils (elles)']
imperative_order = ['tu', 'nous', 'vous']

# Subtenses to skip
skip_subtenses = {
    "Indicatif": ["Passé Simple"],
    "Subjonctif": ["Imparfait"]
}

# Output containers
rows = []
column_tracker = defaultdict(set)
form_columns = [
    "Form__participle_present",
    "Form__participle_past",
    "Form__participle_past_agreement",
    "Form__imperative"
]

for verb in verbs:
    try:
        conj = conjugator.conjugate(verb)
        # print(conj.conjug_info.items())
        flat = {"verb": verb}

        # Extract Participe forms
        participe_data = conj.conjug_info.get("Participe", {})
        flat["Form__participle_present"] = participe_data.get("Participe Présent", "-")

        pp_dict = participe_data.get("Participe Passé", {})
        flat["Form__participle_past"] = pp_dict.get("masculin singulier", "-")

        has_agreement = any(pp_dict.get(k) not in [None, "-", ""] for k in["masculin pluriel", "feminin singulier", "feminin pluriel"])
        flat["Form__participle_past_agreement"] = "+ /-e/-s/-es" if has_agreement else "-"

        # --- Imperatif Handling (simple: always one form, use 'vous') ---
        imperatif_data = conj.conjug_info.get("Imperatif", {}).get("Imperatif Présent", {})
        imperative_form = imperatif_data.get("", None)
        flat["Form__imperative"] = imperative_form if imperative_form else "-"

        # Handle moods
        for mood, mood_data in conj.conjug_info.items():

            # Case 1: mood → subtense → pronoun
            if isinstance(mood_data, Mapping) and all(isinstance(v, Mapping) for v in mood_data.values()):
                for subtense, persons in mood_data.items():
                    if subtense in skip_subtenses.get(mood, []):
                        continue
                    for pronoun in pronoun_order:
                        if pronoun in persons:
                            col = f"{mood}__{subtense}__{pronoun}"
                            flat[col] = persons[pronoun]
                            column_tracker[(mood, subtense)].add(pronoun)

            # Case 2: Imperatif or other flat tense
            elif isinstance(mood_data, Mapping):
                for subtense, persons in mood_data.items():
                    for pronoun in imperative_order:
                        if pronoun in persons:
                            col = f"{mood}__{subtense}__{pronoun}"
                            flat[col] = persons[pronoun]
                            column_tracker[(mood, subtense)].add(pronoun)

        rows.append(flat)

    except Exception as e:
        print(f"❌ Could not conjugate '{verb}': {e}")


# Final output
df_out = pd.DataFrame(rows)
df_out.to_excel("../data/Top_1000_verbs_French_prepared.xlsx", index=False)

# TODO: Find out why 14 verbs are not being conjugated (falloir probably is a difficult exception)
# TODO: Prepare "USE" file automatically with a UserInput and Solution tab, the correct order of columns etc.
