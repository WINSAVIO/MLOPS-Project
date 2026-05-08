import re
import os

def patch_json():
    path = os.path.join('Model Weights', 'generalized_xgboost_model.json')
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return

    print(f"Patching {path}...")
    with open(path, 'r') as f:
        text = f.read()

    # Look for patterns like "[-1.23E-3]" and replace with "-1.23E-3"
    # Also handles "[1.23]"
    new_text = re.sub(r'\"\[(-?\d+\.?\d*E?-?\d*)\]\"', r'"\1"', text)
    
    if new_text != text:
        diff_count = len(re.findall(r'\"\[(-?\d+\.?\d*E?-?\d*)\]\"', text))
        print(f"Found and replaced {diff_count} bracketed values.")
        with open(path, 'w') as f:
            f.write(new_text)
    else:
        print("No bracketed values found to replace.")

if __name__ == "__main__":
    patch_json()
