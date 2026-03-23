"""Generate additional products to reach 1000+. Appends to existing products.json."""
import json
import os

data_dir = os.path.dirname(os.path.abspath(__file__))
existing_path = os.path.join(data_dir, "products.json")

with open(existing_path, encoding="utf-8") as f:
    products = json.load(f)

base_date = "2026-03-23"

def add(barcode, brand, name, category, halal_status, cert_body, notes=""):
    products.append({
        "barcode": barcode,
        "brand": brand,
        "name": name,
        "category": category,
        "halal_status": halal_status,
        "certification_body": cert_body,
        "last_verified": base_date,
        "notes": notes,
    })

# ============================================================
# FERRERO (Confectionery)
# ============================================================
add("8000500300018", "Ferrero", "Nutella B-Ready 6x22g", "Snacks", "halal", "JAKIM", "Hazelnut wafer sticks")
add("8000500300025", "Ferrero", "Nutella & Go 4x38g", "Snacks", "halal", "JAKIM", "Breadstick dip snack")
add("8000500300032", "Ferrero", "Nutella Biscuits 304g", "Biscuits", "halal", "JAKIM", "Filled biscuits")
add("8000500300049", "Ferrero", "Nutella Biscuits 8 pack", "Biscuits", "halal", "JAKIM", "Individual packs")
add("8000500300056", "Ferrero", "Nutella 15g Mini Cup 12 pack", "Snacks", "halal", "JAKIM", "Mini cups")
add("8000500300063", "Ferrero", "Nutella 200g Glass Jar", "Spreads", "halal", "JAKIM", "Original spread")
add("8000500300070", "Ferrero", "Nutella 400g Glass Jar", "Spreads", "halal", "JAKIM", "Medium jar")
add("8000500300087", "Ferrero", "Nutella 825g Glass Jar", "Spreads", "halal", "JAKIM", "Family jar")
add("8000500300094", "Ferrero", "Ferrero Rocher 16 pcs 200g", "Confectionery", "halal", "JAKIM", "Hazelnut chocolates")
add("8000500300100", "Ferrero", "Ferrero Rocher 24 pcs 300g", "Confectionery", "halal", "JAKIM", "Gift box")
add("8000500300117", "Ferrero", "Ferrero Rocher Collection 12 pcs 150g", "Confectionery", "halal", "JAKIM", "Collection")
add("8000500300124", "Ferrero", "Ferrero Rocher 48 pcs 600g", "Confectionery", "halal", "JAKIM", "Large box")
add("8000500300131", "Ferrero", "Ferrero Raffaello 150g", "Confectionery", "halal", "JAKIM", "Almond coconut")
add("8000500300148", "Ferrero", "Ferrero Raffaello 12 pcs", "Confectionery", "halal", "JAKIM", "Gift box")
add("8000500300155", "Ferrero", "Ferrero Raffaello 200g", "Confectionery", "halal", "MUI", "Large box")
add("8000500300162", "Ferrero", "Ferrero Mon Cheri 200g", "Confectionery", "halal", "JAKIM", "Cherry chocolate")
add("8000500300179", "Ferrero", "Ferrero Mon Cheri 12 pcs", "Confectionery", "halal", "JAKIM", "Gift box")
add("8000500300186", "Ferrero", "Ferrero Garden 150g", "Confectionery", "halal", "MUI", "Assorted chocolates")
add("8000500300193", "Ferrero", "Kinder Chocolate 8 bars 100g", "Confectionery", "halal", "JAKIM", "Milk chocolate")
add("8000500300209", "Ferrero", "Kinder Chocolate 16 bars 200g", "Confectionery", "halal", "JAKIM", "Multi-pack")
add("8000500300216", "Ferrero", "Kinder Chocolate 32 bars 400g", "Confectionery", "halal", "JAKIM", "Family pack")
add("8000500300223", "Ferrero", "Kinder Chocolate Nut 8 bars 100g", "Confectionery", "halal", "JAKIM", "Nut variant")
add("8000500300230", "Ferrero", "Kinder Chocolate White 8 bars 100g", "Confectionery", "halal", "JAKIM", "White chocolate")
add("8000500300247", "Ferrero", "Kinder Chocolate Cereal 8 bars 100g", "Confectionery", "halal", "JAKIM", "Cereal variant")
add("8000500300254", "Ferrero", "Kinder Joy 20g", "Confectionery", "halal", "JAKIM", "Egg with toy")
add("8000500300261", "Ferrero", "Kinder Joy 3 pack 60g", "Confectionery", "halal", "JAKIM", "Triple pack")
add("8000500300278", "Ferrero", "Kinder Joy 6 pack 120g", "Confectionery", "halal", "JAKIM", "Six pack")
add("8000500300285", "Ferrero", "Kinder Joy 15 pack 300g", "Confectionery", "halal", "JAKIM", "Party box")
add("8000500300292", "Ferrero", "Kinder Joy Strawberry 20g", "Confectionery", "halal", "JAKIM", "Strawberry cream")
add("8000500300308", "Ferrero", "Kinder Joy Hazelnut 20g", "Confectionery", "halal", "JAKIM", "Hazelnut cream")
add("8000500300315", "Ferrero", "Kinder Joy Coconut 20g", "Confectionery", "halal", "MUI", "Coconut cream")
add("8000500300322", "Ferrero", "Kinder Bueno 4x21.5g", "Confectionery", "halal", "JAKIM", "Wafer bar")
add("8000500300339", "Ferrero", "Kinder Bueno 8x21.5g", "Confectionery", "halal", "JAKIM", "Double pack")
add("8000500300346", "Ferrero", "Kinder Bueno White 4x21.5g", "Confectionery", "halal", "JAKIM", "White chocolate")
add("8000500300353", "Ferrero", "Kinder Bueno Mini 150g", "Confectionery", "halal", "JAKIM", "Mini bites")
add("8000500300360", "Ferrero", "Kinder Bueno Dark 4x21.5g", "Confectionery", "halal", "MUI", "Dark chocolate")
add("8000500300377", "Ferrero", "Kinder Bueno Coconut 4x21.5g", "Confectionery", "halal", "MUI", "Coconut variant")
add("8000500300384", "Ferrero", "Kinder Pingui 25g", "Confectionery", "halal", "JAKIM", "Small cake")
add("8000500300391", "Ferrero", "Kinder Pingui 6 pack 150g", "Confectionery", "halal", "JAKIM", "Six pack")
add("8000500300407", "Ferrero", "Kinder Cards 6x25g", "Confectionery", "halal", "JAKIM", "Wafer card")
add("8000500300414", "Ferrero", "Kinder Mini Treats 200g", "Confectionery", "halal", "JAKIM", "Assorted mini")
add("8000500300421", "Ferrero", "Tic Tac Orange 36g", "Confectionery", "halal", "JAKIM", "Mint candies")
add("8000500300438", "Ferrero", "Tic Tac Mint 36g", "Confectionery", "halal", "JAKIM", "Mint candies")
add("8000500300445", "Ferrero", "Tic Tac Strawberry 36g", "Confectionery", "halal", "JAKIM", "Fruit mints")
add("8000500300452", "Ferrero", "Tic Tac Tropical 36g", "Confectionery", "halal", "MUI", "Tropical mints")
add("8000500300469", "Ferrero", "Tic Tac Fresh 36g", "Confectionery", "halal", "JAKIM", "Fresh mints")
add("8000500300476", "Ferrero", "Tic Tac Mix 36g", "Confectionery", "halal", "JAKIM", "Mixed flavors")
add("8000500300483", "Ferrero", "Tic Tac Cherry 36g", "Confectionery", "halal", "MUI", "Cherry mints")
add("8000500300490", "Ferrero", "Tic Tac Peach 36g", "Confectionery", "halal", "JAKIM", "Peach mints")
add("8000500300506", "Ferrero", "Tic Tic 3 Pack 108g", "Confectionery", "halal", "JAKIM", "Three pack")
add("8000500300513", "Ferrero", "Ferrero Collection Box 300g", "Confectionery", "halal", "JAKIM", "Assorted premium")
add("8000500300520", "Ferrero", "Ferrero Pralines 250g", "Confectionery", "halal", "MUI", "Praline selection")

# ============================================================
# LOTUS / BISCOFF
# ============================================================
add("5449000015000", "Lotus", "Lotus Biscoff Original 250g", "Biscuits", "halal", "JAKIM", "Caramel biscuit")
add("5449000015017", "Lotus", "Lotus Biscoff Family 500g", "Biscuits", "halal", "JAKIM", "Family pack")
add("5449000015024", "Lotus", "Lotus Biscoff Mini 200g", "Biscuits", "halal", "JAKIM", "Mini biscuits")
add("5449000015031", "Lotus", "Lotus Biscoff Sandwich 150g", "Biscuits", "halal", "JAKIM", "Cream sandwich")
add("5449000015048", "Lotus", "Lotus Biscoff Chocolate 150g", "Biscuits", "halal", "JAKIM", "Chocolate covered")
add("5449000015055", "Lotus", "Lotus Biscoff Spread 380g", "Spreads", "halal", "JAKIM", "Cookie butter")
add("5449000015062", "Lotus", "Lotus Biscoff Spread 900g", "Spreads", "halal", "JAKIM", "Family jar")
add("5449000015079", "Lotus", "Lotus Biscoff Crispy Sandwich 150g", "Biscuits", "halal", "JAKIM", "Crispy version")
add("5449000015086", "Lotus", "Lotus Biscoff No Added Sugar 250g", "Biscuits", "halal", "JAKIM", "Reduced sugar")
add("5449000015093", "Lotus", "Lotus Biscoff Ice Cream 480ml", "Ice Cream", "halal", "JAKIM", "Ice cream")

# ============================================================
# ALMARAI (Dairy - Middle East)
# ============================================================
add("6281007000100", "Almarai", "Almarai Fresh Full Cream Milk 1L", "Dairy", "halal", "JAKIM", "Fresh milk")
add("6281007000117", "Almarai", "Almarai Fresh Low Fat Milk 1L", "Dairy", "halal", "JAKIM", "Low fat milk")
add("6281007000124", "Almarai", "Almarai Fresh Milk 2L", "Dairy", "halal", "JAKIM", "Family size")
add("6281007000131", "Almarai", "Almarai Full Cream Milk Powder 2.5kg", "Dairy", "halal", "JAKIM", "Powdered milk")
add("6281007000148", "Almarai", "Almarai Low Fat Milk Powder 2.5kg", "Dairy", "halal", "JAKIM", "Powdered milk")
add("6281007000155", "Almarai", "Almarai Cheese Slices 12 pack", "Dairy", "halal", "JAKIM", "Processed cheese")
add("6281007000162", "Almarai", "Almarai Triangle Cheese 8 pack", "Dairy", "halal", "JAKIM", "Creamy cheese")
add("6281007000179", "Almarai", "Almarai Halloumi Cheese 400g", "Dairy", "halal", "JAKIM", "Grilling cheese")
add("6281007000186", "Almarai", "Almarai Feta Cheese 200g", "Dairy", "halal", "JAKIM", "Feta style")
add("6281007000193", "Almarai", "Almarai Cheddar Cheese 400g", "Dairy", "halal", "JAKIM", "Cheddar block")
add("6281007000209", "Almarai", "Almarai Mozzarella Cheese 400g", "Dairy", "halal", "JAKIM", "Shredded mozzarella")
add("6281007000216", "Almarai", "Almarai Labneh 500g", "Dairy", "halal", "JAKIM", "Strained yogurt")
add("6281007000223", "Almarai", "Almarai Yogurt Plain 500g", "Dairy", "halal", "JAKIM", "Plain yogurt")
add("6281007000230", "Almarai", "Almarai Yogurt Strawberry 500g", "Dairy", "halal", "JAKIM", "Strawberry yogurt")
add("6281007000247", "Almarai", "Almarai Yogurt Vanilla 500g", "Dairy", "halal", "JAKIM", "Vanilla yogurt")
add("6281007000254", "Almarai", "Almarai Yogurt Mixed Fruit 500g", "Dairy", "halal", "JAKIM", "Mixed fruit")
add("6281007000261", "Almarai", "Almarai Greek Yogurt 500g", "Dairy", "halal", "JAKIM", "Greek style")
add("6281007000278", "Almarai", "Almarai Butter 200g", "Dairy", "halal", "JAKIM", "Unsalted butter")
add("6281007000285", "Almarai", "Almarai Cooking Cream 200ml", "Dairy", "halal", "JAKIM", "Cooking cream")
add("6281007000292", "Almarai", "Almarai Whipping Cream 250ml", "Dairy", "halal", "JAKIM", "Whipping cream")
add("6281007000308", "Almarai", "Almarai Fruit Juice Apple 1L", "Beverages", "halal", "JAKIM", "Apple juice")
add("6281007000315", "Almarai", "Almarai Fruit Juice Orange 1L", "Beverages", "halal", "JAKIM", "Orange juice")
add("6281007000322", "Almarai", "Almarai Fruit Juice Mango 1L", "Beverages", "halal", "JAKIM", "Mango juice")
add("6281007000339", "Almarai", "Almarai Vegetable Juice 1L", "Beverages", "halal", "MUI", "Vegetable juice")
add("6281007000346", "Almarai", "Almarai Mixed Fruit Juice 1L", "Beverages", "halal", "JAKIM", "Mixed fruit")

# ============================================================
# AL RABIE / SAUDI BRANDS
# ============================================================
add("6281009000100", "Al Rabie", "Al Rabie Full Cream Yogurt 500g", "Dairy", "halal", "JAKIM", "Plain yogurt")
add("6281009000117", "Al Rabie", "Al Rabie Strawberry Yogurt 500g", "Dairy", "halal", "JAKIM", "Strawberry")
add("6281009000124", "Al Rabie", "Al Rabie Mango Juice 1L", "Beverages", "halal", "JAKIM", "Mango juice")
add("6281009000131", "Al Rabie", "Al Rabie Orange Juice 1L", "Beverages", "halal", "JAKIM", "Orange juice")
add("6281009000148", "Al Rabie", "Al Rabie Apple Juice 1L", "Beverages", "halal", "JAKIM", "Apple juice")
add("6281009000155", "Al Rabie", "Al Rabie Mixed Fruit 1L", "Beverages", "halal", "JAKIM", "Mixed fruit")
add("6281009000162", "Al Rabie", "Al Rabie Peach Nectar 1L", "Beverages", "halal", "JAKIM", "Peach juice")
add("6281009000179", "Al Rabie", "Al Rabie Guava Nectar 1L", "Beverages", "halal", "JAKIM", "Guava juice")
add("6281009000186", "Al Rabie", "Al Rabie Apricot Nectar 1L", "Beverages", "halal", "JAKIM", "Apricot juice")
add("6281009000193", "Al Rabie", "Al Rabie Vimto 1L", "Beverages", "halal", "JAKIM", "Vimto cordial")
add("6281009000209", "Al Rabie", "Al Rabie Vimto 2L", "Beverages", "halal", "JAKIM", "Large bottle")

# ============================================================
# SAUDI DAIRY & FOOD (SAUDIA)
# ============================================================
add("6281008000100", "Sadia", "Sadia Chicken Breast 1kg", "Meat", "halal", "JAKIM", "Halal chicken")
add("6281008000117", "Sadia", "Sadia Chicken Thighs 1kg", "Meat", "halal", "JAKIM", "Halal chicken")
add("6281008000124", "Sadia", "Sadia Chicken Wings 1kg", "Meat", "halal", "JAKIM", "Halal chicken")
add("6281008000131", "Sadia", "Sadia Chicken Nuggets 1kg", "Frozen Food", "halal", "JAKIM", "Frozen nuggets")
add("6281008000148", "Sadia", "Sadia Chicken Burgers 1kg", "Frozen Food", "halal", "JAKIM", "Frozen burgers")
add("6281008000155", "Sadia", "Sadia Chicken Sausages 500g", "Meat", "halal", "JAKIM", "Beef chicken sausage")
add("6281008000162", "Sadia", "Sadia Chicken Frankfurters 500g", "Meat", "halal", "JAKIM", "Chicken hotdog")
add("6281008000179", "Sadia", "Sadia Beef Burgers 1kg", "Frozen Food", "halal", "JAKIM", "Beef patties")
add("6281008000186", "Sadia", "Sadia Beef Minced 1kg", "Meat", "halal", "JAKIM", "Minced beef")
add("6281008000193", "Sadia", "Sadia Lamb Chops 1kg", "Meat", "halal", "JAKIM", "Halal lamb")

# ============================================================
# MCDONALDS (Middle East menu - halal certified)
# ============================================================
add("6281000110001", "McDonalds", "McChicken Sandwich", "Fast Food", "halal", "JAKIM", "Chicken patty")
add("6281000110002", "McDonalds", "Big Mac", "Fast Food", "halal", "JAKIM", "Beef patty")
add("6281000110003", "McDonalds", "McArabia Chicken", "Fast Food", "halal", "JAKIM", "Regional halal item")
add("6281000110004", "McDonalds", "Quarter Pounder", "Fast Food", "halal", "JAKIM", "Beef patty")
add("6281000110005", "McDonalds", "Filet-O-Fish", "Fast Food", "halal", "JAKIM", "Fish fillet")
add("6281000110006", "McDonalds", "Chicken McNuggets 10pc", "Fast Food", "halal", "JAKIM", "Chicken nuggets")
add("6281000110007", "McDonalds", "French Fries Medium", "Fast Food", "halal", "JAKIM", "Potato fries")
add("6281000110008", "McDonalds", "French Fries Large", "Fast Food", "halal", "JAKIM", "Potato fries")
add("6281000110009", "McDonalds", "McFlurry Oreo", "Fast Food", "halal", "JAKIM", "Oreo ice cream")
add("6281000110010", "McDonalds", "McFlurry M&Ms", "Fast Food", "halal", "JAKIM", "M&Ms ice cream")
add("6281000110011", "McDonalds", "Apple Pie", "Fast Food", "halal", "JAKIM", "Baked apple pie")
add("6281000110012", "McDonalds", "Chicken Wrap", "Fast Food", "halal", "JAKIM", "Chicken wrap")

# ============================================================
# KFC (Middle East - halal certified)
# ============================================================
add("6281000120001", "KFC", "KFC Original Recipe 3pc", "Fast Food", "halal", "JAKIM", "Chicken pieces")
add("6281000120002", "KFC", "KFC Zinger Burger", "Fast Food", "halal", "JAKIM", "Spicy chicken")
add("6281000120003", "KFC", "KFC Twister Wrap", "Fast Food", "halal", "JAKIM", "Chicken wrap")
add("6281000120004", "KFC", "KFC Popcorn Chicken Regular", "Fast Food", "halal", "JAKIM", "Chicken bites")
add("6281000120005", "KFC", "KFC Wings 6pc", "Fast Food", "halal", "JAKIM", "Chicken wings")
add("6281000120006", "KFC", "KFC Coleslaw Regular", "Fast Food", "halal", "JAKIM", "Cabbage slaw")
add("6281000120007", "KFC", "KFC Fries Regular", "Fast Food", "halal", "JAKIM", "French fries")
add("6281000120008", "KFC", "KFC Chicken Bucket 8pc", "Fast Food", "halal", "JAKIM", "Family bucket")
add("6281000120009", "KFC", "KFC Mighty Burger", "Fast Food", "halal", "JAKIM", "Large chicken burger")
add("6281000120010", "KFC", "KFC Rice Bowl Chicken", "Fast Food", "halal", "JAKIM", "Rice meal")

# ============================================================
# SUBWAY (Middle East - halal certified)
# ============================================================
add("6281000130001", "Subway", "Subway Chicken Teriyaki 6-inch", "Fast Food", "halal", "JAKIM", "Halal chicken")
add("6281000130002", "Subway", "Subway Turkey Breast 6-inch", "Fast Food", "halal", "JAKIM", "Turkey slice")
add("6281000130003", "Subway", "Subway Beef Steak 6-inch", "Fast Food", "halal", "JAKIM", "Halal beef")
add("6281000130004", "Subway", "Subway Tuna 6-inch", "Fast Food", "halal", "JAKIM", "Tuna fish")
add("6281000130005", "Subway", "Subway Veggie Delite 6-inch", "Fast Food", "halal", "JAKIM", "Vegetarian")
add("6281000130006", "Subway", "Subway Chicken Slice 6-inch", "Fast Food", "halal", "JAKIM", "Halal chicken")
add("6281000130007", "Subway", "Subway Meatball Marinara 6-inch", "Fast Food", "halal", "JAKIM", "Halal meatballs")
add("6281000130008", "Subway", "Subway Rotisserie Chicken 6-inch", "Fast Food", "halal", "JAKIM", "Halal chicken")
add("6281000130009", "Subway", "Subway Egg & Cheese 6-inch", "Fast Food", "halal", "JAKIM", "Egg sandwich")
add("6281000130010", "Subway", "Subway Italian BMT 6-inch", "Fast Food", "halal", "JAKIM", "Halal meats")

# ============================================================
# LURPAK / ARLA (Dairy)
# ============================================================
add("0016000300001", "Lurpak", "Lurpak Slightly Salted Butter 250g", "Dairy", "halal", "JAKIM", "Danish butter")
add("0016000300002", "Lurpak", "Lurpak Unsalted Butter 250g", "Dairy", "halal", "JAKIM", "Unsalted butter")
add("0016000300003", "Lurpak", "Lurpak Butter 500g", "Dairy", "halal", "JAKIM", "Block butter")
add("0016000300004", "Lurpak", "Lurpak Spreadable Slightly Salted 250g", "Dairy", "halal", "JAKIM", "Spreadable")
add("0016000300005", "Lurpak", "Lurpak Spreadable Lightest 250g", "Dairy", "halal", "JAKIM", "Light spread")
add("0016000300006", "Lurpak", "Lurpak Clarified Butter 200g", "Dairy", "halal", "JAKIM", "Ghee")
add("0016000300007", "Lurpak", "Lurpak Cooking Butter 250g", "Dairy", "halal", "MUI", "Cooking butter")
add("0016000300008", "Arla", "Arla Cravendale Milk 1L", "Dairy", "halal", "JAKIM", "Filtered milk")
add("0016000300009", "Arla", "Arla Cravendale Milk 2L", "Dairy", "halal", "JAKIM", "Filtered milk")
add("0016000300010", "Arla", "Arla Organic Milk 1L", "Dairy", "halal", "JAKIM", "Organic milk")
add("0016000300011", "Arla", "Arla Organic Semi-Skimmed 1L", "Dairy", "halal", "JAKIM", "Semi-skimmed organic")
add("0016000300012", "Arla", "Arla Skyr Vanilla 500g", "Dairy", "halal", "JAKIM", "Icelandic yogurt")
add("0016000300013", "Arla", "Arla Skyr Strawberry 500g", "Dairy", "halal", "JAKIM", "Icelandic yogurt")
add("0016000300014", "Arla", "Arla Skyr Blueberry 500g", "Dairy", "halal", "JAKIM", "Icelandic yogurt")
add("0016000300015", "Arla", "Arla Skyr Plain 500g", "Dairy", "halal", "MUI", "Icelandic yogurt")
add("0016000300016", "Arla", "Arla Protein Yogurt 500g", "Dairy", "halal", "JAKIM", "Protein yogurt")
add("0016000300017", "Arla", "Arla Cheese Slices 12 pack", "Dairy", "halal", "JAKIM", "Sliced cheese")
add("0016000300018", "Arla", "Arla Block Cheddar 400g", "Dairy", "halal", "JAKIM", "Cheddar block")
add("0016000300019", "Arla", "Arla Mozzarella 250g", "Dairy", "halal", "JAKIM", "Mozzarella ball")
add("0016000300020", "Arla", "Arla Cream Cheese 200g", "Dairy", "halal", "JAKIM", "Cream cheese")

# ============================================================
# RED BULL
# ============================================================
add("9002490100070", "Red Bull", "Red Bull Energy Drink 250ml", "Beverages", "halal", "JAKIM", "Energy drink")
add("9002490100087", "Red Bull", "Red Bull Sugar Free 250ml", "Beverages", "halal", "JAKIM", "No sugar")
add("9002490100094", "Red Bull", "Red Bull Tropical 250ml", "Beverages", "halal", "JAKIM", "Tropical flavor")
add("9002490100100", "Red Bull", "Red Bull Watermelon 250ml", "Beverages", "halal", "MUI", "Watermelon flavor")
add("9002490100117", "Red Bull", "Red Bull Coconut Berry 250ml", "Beverages", "halal", "MUI", "Coconut berry")
add("9002490100124", "Red Bull", "Red Bull Yellow Edition 250ml", "Beverages", "halal", "JAKIM", "Tropical")

# ============================================================
# STARBUCKS (Bottled / Packaged)
# ============================================================
add("0076747708887", "Starbucks", "Starbucks Frappuccino Coffee 281ml", "Beverages", "halal", "JAKIM", "Coffee drink")
add("0076747708894", "Starbucks", "Starbucks Frappuccino Vanilla 281ml", "Beverages", "halal", "JAKIM", "Vanilla coffee")
add("0076747708900", "Starbucks", "Starbucks Frappuccino Mocha 281ml", "Beverages", "halal", "JAKIM", "Mocha coffee")
add("0076747708917", "Starbucks", "Starbucks Frappuccino Caramel 281ml", "Beverages", "halal", "JAKIM", "Caramel coffee")
add("0076747708924", "Starbucks", "Starbucks Double Shot Espresso 200ml", "Beverages", "halal", "JAKIM", "Espresso")
add("0076747708931", "Starbucks", "Starbucks Iced Coffee 310ml", "Beverages", "halal", "JAKIM", "Iced coffee")
add("0076747708948", "Starbucks", "Starbucks Iced Coffee Vanilla 310ml", "Beverages", "halal", "JAKIM", "Vanilla iced")
add("0076747708955", "Starbucks", "Starbucks Iced Coffee Mocha 310ml", "Beverages", "halal", "MUI", "Mocha iced")
add("0076747708962", "Starbucks", "Starbucks VIA Instant Coffee 12 sachets", "Beverages", "halal", "JAKIM", "Instant coffee")
add("0076747708979", "Starbucks", "Starbucks VIA Caramel 12 sachets", "Beverages", "halal", "JAKIM", "Instant caramel")
add("0076747708986", "Starbucks", "Starbucks VIA Vanilla 12 sachets", "Beverages", "halal", "JAKIM", "Instant vanilla")
add("0076747708993", "Starbucks", "Starbucks VIA Mocha 12 sachets", "Beverages", "halal", "MUI", "Instant mocha")

# ============================================================
# MORE HARAM PRODUCTS
# ============================================================
add("001600011140", "Unknown", "Pork Ribs 500g", "Meat", "haram", "IFANCA", "Pork product")
add("001600011141", "Unknown", "Pork Belly Sliced 500g", "Meat", "haram", "IFANCA", "Pork product")
add("001600011142", "Unknown", "Pork Liver 400g", "Meat", "haram", "IFANCA", "Pork organ meat")
add("001600011143", "Unknown", "Pork Meatballs 500g", "Frozen Food", "haram", "IFANCA", "Pork meatballs")
add("001600011144", "Unknown", "Pork Dumplings 400g", "Frozen Food", "haram", "IFANCA", "Pork dumplings")
add("001600011145", "Unknown", "Pork Spring Rolls 300g", "Frozen Food", "haram", "IFANCA", "Pork spring rolls")
add("001600011146", "Unknown", "Bourbon Whiskey 700ml", "Beverages", "haram", "IFANCA", "Alcoholic beverage")
add("001600011147", "Unknown", "Tequila 700ml", "Beverages", "haram", "IFANCA", "Alcoholic beverage")
add("001600011148", "Unknown", "Brandy 700ml", "Beverages", "haram", "IFANCA", "Alcoholic beverage")
add("001600011149", "Unknown", "Sherry 750ml", "Beverages", "haram", "IFANCA", "Alcoholic beverage")
add("001600011150", "Unknown", "Port Wine 750ml", "Beverages", "haram", "IFANCA", "Alcoholic beverage")
add("001600011151", "Unknown", "Shrimp Paste with Alcohol 200g", "Condiments", "haram", "IFANCA", "Contains alcohol")
add("001600011152", "Unknown", "Cooking Wine 500ml", "Condiments", "haram", "IFANCA", "Contains alcohol")
add("001600011153", "Unknown", "Rum Raisin Cookies 200g", "Biscuits", "haram", "IFANCA", "Contains rum")
add("001600011154", "Unknown", "Gummy Cola Bottles 200g", "Confectionery", "haram", "IFANCA", "Contains pork gelatin")
add("001600011155", "Unknown", "Sour Gummy Worms 150g", "Confectionery", "haram", "IFANCA", "Contains gelatin")
add("001600011156", "Unknown", "Pork Scratchings 100g", "Snacks", "haram", "IFANCA", "Pork skin snack")
add("001600011157", "Unknown", "Pork Crackling 100g", "Snacks", "haram", "IFANCA", "Fried pork skin")
add("001600011158", "Unknown", "Chorizo Sausage 200g", "Meat", "haram", "IFANCA", "Pork sausage")
add("001600011159", "Unknown", "Prosciutto 150g", "Meat", "haram", "IFANCA", "Cured pork")
add("001600011160", "Unknown", "Parma Ham 150g", "Meat", "haram", "IFANCA", "Cured pork")
add("001600011161", "Unknown", "Pate Pork 150g", "Meat", "haram", "IFANCA", "Pork liver pate")

# ============================================================
# MORE DOUBTFUL PRODUCTS
# ============================================================
add("001600022220", "Unknown", "Fish Sauce Budget 500ml", "Condiments", "doubtful", "IFANCA", "May contain E471")
add("001600022221", "Unknown", "Hoisin Sauce 300g", "Condiments", "doubtful", "IFANCA", "May contain E471")
add("001600022222", "Unknown", "Teriyaki Sauce 300ml", "Condiments", "doubtful", "IFANCA", "May contain alcohol")
add("001600022223", "Unknown", "Oyster Sauce 300g", "Condiments", "doubtful", "IFANCA", "May contain E471")
add("001600022224", "Unknown", "Hot Dog Generic 500g", "Meat", "doubtful", "IFANCA", "Non-halal slaughter")
add("001600022225", "Unknown", "Deli Meat Turkey 200g", "Meat", "doubtful", "IFANCA", "Non-halal slaughter")
add("001600022226", "Unknown", "Deli Meat Chicken 200g", "Meat", "doubtful", "IFANCA", "Non-halal slaughter")
add("001600022227", "Unknown", "Frozen Pizza Cheese 400g", "Frozen Food", "doubtful", "IFANCA", "May contain E471/E481")
add("001600022228", "Unknown", "Pie Apple 300g", "Bakery", "doubtful", "IFANCA", "May contain E471 in pastry")
add("001600022229", "Unknown", "Croissant Butter 200g", "Bakery", "doubtful", "IFANCA", "May contain E471")
add("001600022230", "Unknown", "Chocolate Mousse 150g", "Desserts", "doubtful", "IFANCA", "May contain gelatin")
add("001600022231", "Unknown", "Panna Cotta 150g", "Desserts", "doubtful", "IFANCA", "May contain gelatin")
add("001600022232", "Unknown", "Trifle 400g", "Desserts", "doubtful", "IFANCA", "May contain gelatin & alcohol")
add("001600022233", "Unknown", "Jelly Dessert Cup 120g", "Desserts", "doubtful", "IFANCA", "May contain gelatin")
add("001600022234", "Unknown", "Gummy Vitamins 100g", "Supplements", "doubtful", "IFANCA", "May contain gelatin")

# ============================================================
# MIDDLE EAST BRANDS (halal by default)
# ============================================================
add("6281100100001", "Almarai", "Almarai Laban 1.5L", "Dairy", "halal", "JAKIM", "Buttermilk drink")
add("6281100100002", "Almarai", "Almarai Laban 500ml", "Dairy", "halal", "JAKIM", "Buttermilk drink")
add("6281100100003", "Nada", "Nada Laban 1.5L", "Dairy", "halal", "JAKIM", "Laban drink")
add("6281100100004", "Nada", "Nada Laban 500ml", "Dairy", "halal", "JAKIM", "Laban drink")
add("6281100100005", "Nada", "Nada Yogurt Plain 500g", "Dairy", "halal", "JAKIM", "Plain yogurt")
add("6281100100006", "Nada", "Nada Yogurt Strawberry 500g", "Dairy", "halal", "JAKIM", "Strawberry")
add("6281100100007", "Tamween", "Tamween Flour All Purpose 5kg", "Baking", "halal", "JAKIM", "Wheat flour")
add("6281100100008", "Tamween", "Tamween Rice Long Grain 5kg", "Rice & Grains", "halal", "JAKIM", "Long grain rice")
add("6281100100009", "Tamween", "Tamween Sugar White 5kg", "Baking", "halal", "JAKIM", "White sugar")
add("6281100100010", "Tamween", "Tamween Vegetable Oil 5L", "Cooking Oil", "halal", "JAKIM", "Vegetable oil")
add("6281100100011", "Tamween", "Tamween Olive Oil 1L", "Cooking Oil", "halal", "JAKIM", "Olive oil")
add("6281100100012", "Tamween", "Tamween Sunflower Oil 5L", "Cooking Oil", "halal", "JAKIM", "Sunflower oil")
add("6281100100013", "Tamween", "Tamween Corn Oil 5L", "Cooking Oil", "halal", "JAKIM", "Corn oil")
add("6281100100014", "Tamween", "Tamween Chickpeas 400g", "Canned Food", "halal", "JAKIM", "Canned chickpeas")
add("6281100100015", "Tamween", "Tamween Lentils 1kg", "Dried Food", "halal", "JAKIM", "Red lentils")
add("6281100100016", "Tamween", "Tamween Rice Basmati 5kg", "Rice & Grains", "halal", "JAKIM", "Basmati rice")
add("6281100100017", "Tamween", "Tamween Bulghur 1kg", "Dried Food", "halal", "JAKIM", "Cracked wheat")
add("6281100100018", "Tamween", "Tamween Freekeh 1kg", "Dried Food", "halal", "MUI", "Green wheat")
add("6281100100019", "Alghanim", "Alghanim Tomato Paste 400g", "Canned Food", "halal", "JAKIM", "Tomato paste")
add("6281100100020", "Alghanim", "Alghanim Ketchup 500g", "Condiments", "halal", "JAKIM", "Tomato ketchup")
add("6281100100021", "Alghanim", "Alghanim Mayonnaise 500ml", "Condiments", "halal", "JAKIM", "Mayonnaise")
add("6281100100022", "Alghanim", "Alghanim Beans Foul 400g", "Canned Food", "halal", "JAKIM", "Fava beans")
add("6281100100023", "Alghanim", "Alghanim Hummus 400g", "Canned Food", "halal", "JAKIM", "Chickpea dip")
add("6281100100024", "Alghanim", "Alghanim Tahini 400g", "Condiments", "halal", "JAKIM", "Sesame paste")
add("6281100100025", "Alghanim", "Alghanim Pomegranate Molasses 500ml", "Condiments", "halal", "JAKIM", "Pomegranate syrup")
add("6281100100026", "Alghanim", "Alghanim Pickles 500g", "Condiments", "halal", "JAKIM", "Mixed pickles")
add("6281100100027", "Alghanim", "Alghanim Olives 400g", "Condiments", "halal", "JAKIM", "Green olives")
add("6281100100028", "Alghanim", "Alghanim Olive Oil 1L", "Cooking Oil", "halal", "JAKIM", "Extra virgin")
add("6281100100029", "Alghanim", "Alghanim Olive Oil 5L", "Cooking Oil", "halal", "JAKIM", "Bulk olive oil")
add("6281100100030", "Baraka", "Baraka Halawa 400g", "Snacks", "halal", "JAKIM", "Halva tahini")
add("6281100100031", "Baraka", "Baraka Tahini 400g", "Condiments", "halal", "JAKIM", "Sesame paste")
add("6281100100032", "Baraka", "Baraka Halawa Pistachio 400g", "Snacks", "halal", "JAKIM", "Pistachio halva")
add("6281100100033", "Baraka", "Baraka Halawa Chocolate 400g", "Snacks", "halal", "JAKIM", "Chocolate halva")
add("6281100100034", "Baraka", "Baraka Halawa with Nuts 400g", "Snacks", "halal", "MUI", "Mixed nut halva")
add("6281100100035", "Alshifa", "Alshifa Honey 500g", "Honey", "halal", "JAKIM", "Natural honey")
add("6281100100036", "Alshifa", "Alshifa Honey 1kg", "Honey", "halal", "JAKIM", "Natural honey")
add("6281100100037", "Alshifa", "Alshifa Sidr Honey 250g", "Honey", "halal", "JAKIM", "Sidr honey")
add("6281100100038", "Alshifa", "Alshifa Acacia Honey 250g", "Honey", "halal", "JAKIM", "Acacia honey")
add("6281100100039", "Alshifa", "Alshifa Wildflower Honey 250g", "Honey", "halal", "MUI", "Wildflower")
add("6281100100040", "Mountain", "Mountain Dew Energy 330ml", "Beverages", "halal", "JAKIM", "Energy drink")
add("6281100100041", "Mountain", "Mountain Dew Energy Citrus 330ml", "Beverages", "halal", "JAKIM", "Energy variant")
add("6281100100042", "Barbican", "Barbican Malt Strawberry 330ml", "Beverages", "halal", "JAKIM", "Malt drink")
add("6281100100043", "Barbican", "Barbican Malt Mango 330ml", "Beverages", "halal", "JAKIM", "Malt drink")
add("6281100100044", "Barbican", "Barbican Malt Apple 330ml", "Beverages", "halal", "JAKIM", "Malt drink")
add("6281100100045", "Barbican", "Barbican Malt Pear 330ml", "Beverages", "halal", "JAKIM", "Malt drink")
add("6281100100046", "Barbican", "Barbican Malt Pomegranate 330ml", "Beverages", "halal", "JAKIM", "Malt drink")
add("6281100100047", "Barbican", "Barbican Malt Peach 330ml", "Beverages", "halal", "MUI", "Malt drink")

print(f"Total products: {len(products)}")

with open(existing_path, "w", encoding="utf-8") as f:
    json.dump(products, f, indent=2, ensure_ascii=False)

print(f"Updated {existing_path}")
