"""Controlled vocabularies shared across apps (single source of truth)."""

ALLERGENS = [
    ("milk", "Milk / dairy"), ("egg", "Egg"), ("peanut", "Peanut"), ("tree_nut", "Tree nuts"),
    ("soy", "Soy"), ("wheat_gluten", "Wheat / gluten"), ("fish", "Fish"),
    ("shellfish", "Shellfish"), ("sesame", "Sesame"), ("mustard", "Mustard"),
]
ALLERGEN_CODES = [code for code, _ in ALLERGENS]

# Descriptive labels only - they make no medical claim.
DIETARY_TAGS = [
    ("vegetarian", "Vegetarian"), ("vegan", "Vegan"), ("eggetarian", "Eggetarian"),
    ("non_vegetarian", "Non-vegetarian"), ("jain", "Jain"), ("gluten_free", "Gluten-free"),
    ("lactose_free", "Lactose-free"), ("high_protein", "High protein"), ("low_carb", "Low carbohydrate"),
    ("low_fat", "Low fat"), ("high_fibre", "High fibre"),
]
DIETARY_TAG_CODES = [code for code, _ in DIETARY_TAGS]

INGREDIENT_CATEGORIES = [
    ("cereal", "Cereals & millets"), ("pulse", "Pulses & legumes"), ("vegetable", "Vegetables"),
    ("fruit", "Fruits"), ("dairy", "Dairy"), ("egg", "Eggs"), ("meat_fish", "Meat, poultry & fish"),
    ("oil_fat", "Oils & fats"), ("nut_seed", "Nuts & seeds"), ("spice", "Spices & condiments"),
    ("sweetener", "Sugar & sweeteners"), ("beverage", "Beverages"), ("other", "Other"),
]

MEAL_CATEGORY_CHOICES = [
    ("breakfast", "Breakfast"), ("mid_morning", "Mid-morning"), ("lunch", "Lunch"),
    ("evening_snack", "Evening snack"), ("dinner", "Dinner"), ("any", "Any meal"),
]
DEFAULT_MEAL_CATEGORIES = [
    ("breakfast", "Breakfast"), ("mid_morning", "Mid-morning"), ("lunch", "Lunch"),
    ("evening_snack", "Evening snack"), ("dinner", "Dinner"),
]

QUANTITY_UNITS = [("g", "grams"), ("ml", "millilitres"), ("piece", "piece")]
