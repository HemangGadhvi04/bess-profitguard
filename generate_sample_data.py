from pathlib import Path

from backend.app.services.data_generator import generate_sample_data


if __name__ == "__main__":
    written = generate_sample_data(Path("data"))
    print("Generated sample datasets:")
    for name, path in written.items():
        print(f"- {name}: {path}")
