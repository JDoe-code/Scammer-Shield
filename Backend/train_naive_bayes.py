import os
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

def train_and_evaluate_model():
    # 1. Locate and parse dataset
    data_file = "data/ocr_results.txt"
    if not os.path.exists(data_file):
        if os.path.exists("../ocr_results.txt"):
            data_file = "../ocr_results.txt"
        else:
            print(f"Error: Could not find '{data_file}' in root or parent directories.")
            return

    labels = []
    texts = []

    print(f"Reading dataset from {data_file}...")
    with open(data_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    email_blocks = content.split("<<<START OF EMAIL>>>")
    for block in email_blocks:
        if "<<<END OF EMAIL>>>" not in block or "LABEL:" not in block:
            continue
            
        lines = block.split("\n")
        label = None
        is_clean_text = False
        text_lines = []
        
        for line in lines:
            if line.startswith("LABEL:"):
                # Explicitly parse based on explicit 0 vs 1 indicators to avoid ambiguity
                if "LABEL:   0" in line or "(legit)" in line.lower():
                    label = "legit"
                elif "LABEL:   1" in line or "(phishing)" in line.lower():
                    label = "phishing"
            elif "----------------------------- CLEAN TEXT -----------------------------" in line:
                is_clean_text = True
                continue
            elif "<<<END OF EMAIL>>>" in line:
                is_clean_text = False
                
            if is_clean_text:
                text_lines.append(line.strip())
        print("Sample Parsed Texts:", list(zip(labels[:3], texts[:3])))
        clean_text = " ".join(text_lines).strip()
        if label and clean_text:
            labels.append(label)
            texts.append(clean_text)

    print(f"Successfully parsed {len(texts)} total emails.")

    if len(texts) == 0:
        print("Warning: No texts found to train on.")
        return

    # 2. Perform 80/10/10 Split (Train / Validation / Test)
    X_train, X_temp, y_train, y_temp = train_test_split(
        texts, labels, test_size=0.20, random_state=42, stratify=labels
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    print(f"\nDataset Splits:")
    print(f"  - Training Set:   {len(X_train)} samples")
    print(f"  - Validation Set: {len(X_val)} samples")
    print(f"  - Test Set:       {len(X_test)} samples\n")

    # 3. Build and Train Model Pipeline
    print("Training Naive Bayes classifier...")
    model = make_pipeline(TfidfVectorizer(), MultinomialNB())
    model.fit(X_train, y_train)
    print("Training complete!")

    # 4. Evaluate on Test Set
    test_preds = model.predict(X_test)
    acc = accuracy_score(y_test, test_preds)
    conf_matrix = confusion_matrix(y_test, test_preds, labels=['legit', 'phishing'])
    class_report_str = classification_report(y_test, test_preds, target_names=['legit', 'phishing'])

    # Print to terminal
    print("\n==========================================")
    print("       TEST SET EVALUATION METRICS        ")
    print("==========================================")
    print(f"Overall Accuracy: {acc * 100:.2f}%\n")
    print("Confusion Matrix:")
    print(conf_matrix)
    print("\nDetailed Classification Report:")
    print(class_report_str)

    # 5. Save Evaluation Report to a Text File
    os.makedirs("models", exist_ok=True)
    report_path = "models/evaluation_report.txt"
    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write("==========================================\n")
        report_file.write("       TEST SET EVALUATION METRICS        \n")
        report_file.write("==========================================\n")
        report_file.write(f"Overall Accuracy: {acc * 100:.2f}%\n\n")
        report_file.write("Confusion Matrix:\n")
        report_file.write(str(conf_matrix) + "\n\n")
        report_file.write("Detailed Classification Report:\n")
        report_file.write(class_report_str)
    print(f"Evaluation report successfully saved to '{report_path}'!")

    # 6. Generate and Save Confusion Matrix Visualization
    plt.figure(figsize=(6, 5))
    sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['legit', 'phishing'], 
                yticklabels=['legit', 'phishing'])
    plt.title('Scam Detector - Confusion Matrix')
    plt.xlabel('Predicted Label')
    plt.ylabel('Actual Label')
    plt.tight_layout()
    
    plot_path = "models/confusion_matrix.png"
    plt.savefig(plot_path)
    plt.close()
    print(f"Confusion matrix plot successfully saved to '{plot_path}'!")

    # 7. Save Model Object via joblib
    model_path = "models/scam_detector.pkl"
    joblib.dump(model, model_path)
    print(f"Model successfully saved to '{model_path}'!")

if __name__ == "__main__":
    train_and_evaluate_model()