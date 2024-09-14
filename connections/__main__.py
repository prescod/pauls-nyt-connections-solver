import json
from pathlib import Path
from pprint import pprint
from random import Random
from tempfile import gettempdir
import diskcache
import litellm
from litellm import completion, Cache
import argparse
from pydantic import BaseModel


PROMPT = """
Find groups of four items that share something in common.
Category Examples

FISH: Bass, Flounder, Salmon, Trout
FIRE ___:
Ant, Drill, Island, Opal
Categories will always be more specific than
"5-LETTER-WORDS," "NAMES" or "VERBS."

Each puzzle has exactly one solution. Every item fits in
exactly one category.

Watch out for words that seem to belong to multiple categories!

Order your answers in terms of your confidence level, high
confidence first.

Here are the items:

%(items)s

%(error_str)s
Return your guess as ONLY JSON like this:

{"groups":
    [
        {"items": ["item1a", "item2a", "item3a", "item4a"],
            "reason": "..."},
            {"items": ["item2a", "item2b", "item3b", "item4b"],
            "reason": "..."},
    ]}

No other text.
"""

litellm.cache = Cache(type="disk")


class ConnectionsGuess(BaseModel):
    items: list[str]
    reason: str


class ConnectionsGuesses(BaseModel):
    groups: list[ConnectionsGuess]


def format_list(lst):
    return ",".join([f'"{item}"' for item in lst])


def format_errors(errors):

    errors = "\n".join([format_list(e) for e in errors])
    error_str = (
        f"You previously guessed \n{errors}\n"
        "Those answers are not correct. Do not repeat them.\n"
    )
    return error_str


cache = diskcache.Cache(Path(gettempdir()) / "litellm_cache")


@cache.memoize()
def call_llm(model: str, prompt, items: list[str], error: list[list[str]] = []):

    error_str = format_errors(error) if error else ""

    prompt = prompt % {
        "items": ",".join(items),
        "error_str": error_str,
    }
    print(prompt)

    message = {"role": "user", "content": prompt}
    resp = completion(
        model=model,
        temperature=1,
        messages=[message],
    )

    content = resp.choices[0].message.content
    content = content.removeprefix("```json").removesuffix("```").strip()
    print("  <=======")
    print(content)
    data = ConnectionsGuesses(**json.loads(content))
    return data


r = Random(0xDEADBEEF)


def run_connections(model: str, correct_answers=list[list[str]]):
    answer_sheet = set(frozenset(a) for a in correct_answers)

    remaining_words = set.union(*(set(a) for a in correct_answers))
    correct_sets = []
    errors = []
    while remaining_words and len(errors) < 4:
        print("\n\n*********\n\n")
        wordlist = sorted(remaining_words)
        r.shuffle(wordlist)
        result = call_llm(model, PROMPT, wordlist, errors)
        print("\n")
        pprint(result)
        print("\n")
        groups = result.groups
        for group in groups:
            items = group.items
            if set(items) in answer_sheet:
                print("Correct!", items)
                remaining_words -= set(items)
                correct_sets.append(set(items))
            else:
                print("Incorrect!", items)
                errors.append(items)
                break  # quit after first error

    if not remaining_words:
        print("All words connected!")
        print("Guesses remaining", 4 - len(errors))
    else:
        print("Failed to connect all words")
        print(
            "Correctly found words:",
            correct_sets,
        )
        print("Remaining words:", remaining_words)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=str, help="AI model to use")
    parser.add_argument("string1", type=str, help="4 Comma-separated items")
    parser.add_argument("string2", type=str, help="4 Comma-separated items")
    parser.add_argument("string3", type=str, help="4 Comma-separated items")
    parser.add_argument("string4", type=str, help="4 Comma-separated items")
    args = parser.parse_args()

    group1 = [w.strip() for w in args.string1.split(",")]
    group2 = [w.strip() for w in args.string2.split(",")]
    group3 = [w.strip() for w in args.string3.split(",")]
    group4 = [w.strip() for w in args.string4.split(",")]

    correct_answers = [group1, group2, group3, group4]

    run_connections(args.model, correct_answers)


if __name__ == "__main__":
    main()
