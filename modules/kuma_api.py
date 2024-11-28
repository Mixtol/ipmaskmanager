import requests
import json

class KumaRestAPIv2:
    #### Класс для работы с API v2.1 #####
    """Данные методы появились только в 3.2 версии
    тут используется только Bearer токен и нет сессий и печеней
    """
    def __init__(self, url, token, cert=None):
        self.session = requests.Session()
        self.session.verify = False
        self.url = url + ':7223'
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _make_request(self, method: str, endpoint: str, data = None, params = None) -> requests.Response:
        """
        Общий метод для выполнения HTTP-запросов.
        :param method: HTTP-метод (GET, POST, PUT, DELETE и т.д.)
        :param endpoint: конечная точка API
        :param data: данные для отправки в теле запроса (для POST, PUT)
        :param params: параметры запроса (для GET)
        :return: объект Response
        """
        url = f"{self.url}/api/v2.1/{endpoint}"
        response = self.session.request(method, url, json=data, params=params)
        if response.status_code in [200, 204]:
            try:
                return response.status_code, response.json()
            except json.JSONDecodeError: # Для CSV ответов
                return response.status_code, response.text
        else:
            return response.status_code, response.text
        
    ####### РАБОТА С СЛОВАРЯИ/ТАБЛИЦАМИ #######

    def add_dictionary_row(self, dictionary_id:str, key:str, data:dict,
                           overwriteExist:int=0, needReload:int=0):
        """Метод создания записи в словаре
        Args:
            dictionary_id (str): UUID
            key (str): уникальный ключ
            data (dict): {
                "Колонна1": "string",
                "Колонна2": "string",
                "Колонна3": "string"
                }'
            overwriteExist (int, optional): 1 если перезаписать ключ. Defaults to 0.
            needReload (int, optional): 1 перезагрузить корреляторы сразу. Defaults to 0.
        """
        params = {
            "dictionaryID": dictionary_id,
            "rowKey":key,
            "overwriteExist":overwriteExist,
            "needReload":needReload
        }
        return self._make_request('POST', f'dictionaries/add_row', params=params, data=data)