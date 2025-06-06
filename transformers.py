


class AutoTokenizer():
    def __init__(self, model_name : str):
        self.model_name = model_name
    def __call__(self, text : str):
        return text
    
class AutoModel():        
    def __init__(self, model_name : str):
        self.model_name = model_name
    def __call__(self, text : str):
        return text