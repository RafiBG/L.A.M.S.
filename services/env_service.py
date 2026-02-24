from pathlib import Path


class EnvService:
    def __init__(self, path: str = ".env"):
        self.path = Path(path)

    def read_raw_lines(self):
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return f.readlines()

    def read(self) -> dict:
        data = {}
        lines = self.read_raw_lines()

        for line in lines:
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            data[key] = value

        return data

    def write_selected(self, updates: dict):
        lines = self.read_raw_lines()
        new_lines = []

        for line in lines:
            stripped = line.strip()

            if not stripped or stripped.startswith("#") or "=" not in stripped:
                new_lines.append(line)
                continue

            key, _ = stripped.split("=", 1)

            if key in updates:
                # Convert real newlines into the text "\n" 
                # before writing to the file so the whole variable stays on ONE line.
                value = str(updates[key]).replace("\n", "\\n").replace("\r", "")
                new_lines.append(f"{key}={value}\n")
            else:
                new_lines.append(line)

        # Handle keys that might not exist in the file yet
        existing_keys = {line.split("=", 1)[0].strip() for line in lines if "=" in line and not line.startswith("#")}
        for key, value in updates.items():
            if key not in existing_keys:
                formatted_value = str(value).replace("\n", "\\n").replace("\r", "")
                new_lines.append(f"{key}={formatted_value}\n")

        with open(self.path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
