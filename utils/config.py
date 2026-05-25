import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "config.json")

DEFAULTS = {
    "always_on_top": True,
    "dark_theme": True,
    "opacity": 0.95,
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return DEFAULTS.copy()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = DEFAULTS.copy()
        data.update(json.load(f))
        return data


def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
