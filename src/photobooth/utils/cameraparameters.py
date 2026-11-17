def resolve_extreme_choice(value, choices: list):
    """a value of 'min' or 'max' selects the smallest/largest numeric choice offered by the camera
    (e.g. aperture 'min' = widest opening, shutterspeed 'max' = longest time). Other values are returned unchanged."""
    if value not in ("min", "max"):
        return value

    def number(choice):
        text = str(choice)
        try:
            if "/" in text:
                num, den = text.split("/", 1)
                return float(num) / float(den)
            return float(text)
        except ValueError:
            return None

    numeric = [(number(c), c) for c in choices if number(c) is not None]
    if not numeric:
        return value
    return (min if value == "min" else max)(numeric, key=lambda item: item[0])[1]
