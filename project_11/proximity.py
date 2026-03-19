# project_11/proximity.py

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CONCEPTS = {
    "user_authentication": {
        "description": "User accounts, passwords, sessions, roles, permissions",
        "aliases":     ["user auth", "login", "sign up", "registration",
                        "authentication", "authorization", "roles",
                        "permissions", "access control"],
    },
    "product_catalog": {
        "description": "Products, categories, attributes, images, pricing",
        "aliases":     ["products", "catalog", "items", "SKUs",
                        "merchandise", "goods"],
    },
    "e_commerce_orders": {
        "description": "Shopping cart, checkout, order lifecycle, order items",
        "aliases":     ["orders", "shopping cart", "checkout",
                        "e-commerce", "online store"],
    },
    "inventory_management": {
        "description": "Warehouses, stock entries, stock ledger, reorder levels",
        "aliases":     ["inventory", "stock", "warehouse",
                        "stock management"],
    },
    "customer_management": {
        "description": "Customer records, addresses, groups, contacts",
        "aliases":     ["customers", "CRM", "contacts",
                        "client management"],
    },
    "employee_management": {
        "description": "Employee records, departments, designations",
        "aliases":     ["employees", "HR", "human resources",
                        "staff", "workforce"],
    },
    "project_tracking": {
        "description": "Projects, tasks, time logs, milestones",
        "aliases":     ["projects", "tasks", "time tracking",
                        "sprints", "milestones"],
    },
}

# ── Build TF-IDF index ─────────────────────────────────────────────────────────

def build_search_index():
    concept_names = []
    corpus        = []

    for name, data in CONCEPTS.items():
        text = data["description"] + " " + " ".join(data["aliases"])
        concept_names.append(name)
        corpus.append(text)

    vectorizer   = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)

    return concept_names, vectorizer, tfidf_matrix

# ── Find nearest concepts ──────────────────────────────────────────────────────

def find_nearest(query, concept_names, vectorizer, tfidf_matrix,
                 top_k=3, min_score=0.1):

    query_vec    = vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, tfidf_matrix)[0]

    scored = [
        (concept_names[i], round(similarities[i], 3))
        for i in range(len(concept_names))
    ]
    scored.sort(key=lambda x: -x[1])

    return [
        (name, score)
        for name, score in scored[:top_k]
        if score >= min_score
    ]

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    names, vectorizer, matrix = build_search_index()

    test_queries = [
        "logistics management",
        "staff directory and departments",
        "online marketplace",
        "IoT device telemetry",
        "task tracking and sprints",
        "patient records",
        "buying things on the internet",
    ]

    print("=" * 60)
    print("Semantic Proximity Search")
    print("=" * 60)

    for query in test_queries:
        results = find_nearest(query, names, vectorizer, matrix)
        print(f"\nQuery: '{query}'")

        if results:
            for name, score in results:
                if score > 0.3:
                    confidence = "high"
                elif score > 0.15:
                    confidence = "medium"
                else:
                    confidence = "low"
                print(f"  → {name:30} similarity={score} ({confidence})")
        else:
            print(f"  → No matches above threshold")