import requests
import json

class ArcSightAPI:
    def __init__(self, url, token):
        self.url = url + ':8443'
        self.verify = False
        self.header = {"Authorization": f"Bearer {token}"}

    def _make_request(self, method: str, endpoint: str, data = None, params = None) -> requests.Response:
        """
        Общий метод для выполнения HTTP-запросов.
        :param method: HTTP-метод (GET, POST, PUT, DELETE и т.д.)
        :param endpoint: конечная точка API
        :param data: данные для отправки в теле запроса (для POST, PUT)
        :param params: параметры запроса (для GET)
        :return: объект Response
        """
        url = f"{self.url}/detect-api/rest/{endpoint}"
        response = requests.request(
            method=method,
            url=url,
            headers=self.header,
            json=data,
            params=params,
            verify=self.verify)
        try:
            response.raise_for_status()
            return response.status_code, response.json()
        except:
            return response.status_code, response.text
    
    def add_list_row(self, dict_id:str, fields_names:list, fields_data:list):
        """Метод добавления записи в АркСайт
        Args:
            dict_id (str): URL Like resourseID
            fields_names (list): список наименованяи полей
            fields_data (list): (В том же порядке что и наименования!) значения полей
        Returns:
            str|"": если создался то пустая строка возвращается
        """
        endpoint = f'activelists/{dict_id}/entries'
        data = {
            "fields":fields_names,
            "entries": [
                {"fields": fields_data}
            ]
        }
        return self._make_request('POST', endpoint, data=data)
