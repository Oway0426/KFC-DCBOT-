import json
import spacy
from spacy.training.example import Example
from tqdm import tqdm


spacy.require_gpu()
print("spaCy is successfully using GPU!")

with open("train_data_updated.json", "r", encoding="utf-8") as f:
    data = json.load(f)


TRAIN_DATA = [
    (item["text"], {"entities": [(ent[0], ent[1], ent[2]) for ent in item["entities"]]})
    for item in data
]


nlp = spacy.blank("zh")
ner = nlp.add_pipe("ner", last=True)  

ner.add_label("QUANTITY")
ner.add_label("FOOD")

EPOCHS = 100
optimizer = nlp.begin_training() 

# 訓練模型
with tqdm(total=EPOCHS, desc="Training Progress") as pbar:
    for epoch in range(EPOCHS):
        losses = {}  
        examples = [] 

        for text, annotations in TRAIN_DATA:
            doc = nlp.make_doc(text)
            example = Example.from_dict(doc, annotations)
            examples.append(example)
        nlp.update(examples, drop=0.3, losses=losses)
        pbar.set_postfix(loss=losses)
        pbar.update(1)

nlp.to_disk("custom_ner_model")
