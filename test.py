from mftool import Mftool
import json

mf = Mftool()
all_schemes = mf.get_scheme_codes()
# Save all schemes to a JSON file
with open("all_schemes.json", "w") as f:
    json.dump(all_schemes, f, indent=4)