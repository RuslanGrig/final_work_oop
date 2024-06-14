import requests
import datetime
import json
import logging

class VK:
    
    api_url = 'https://api.vk.com/method'
    def __init__(self, access_token, user_id):
        self.token = access_token
        self.id = user_id 
    
    def _get_common_params(self):
        return {                
            'access_token': self.token,
            'v': '5.199',
            'owner_id': self.id,
            'album_id': 'profile',
            'photo_sizes': '1',            
            'extended': '1',
            'rev': '1'            
        }
    
    def _max_size(self, photo_size_list):        
        type_list = ['w', 'z', 'y', 'x', 'm', 's']
        for size_type in type_list:
            if size_type in photo_size_list:
                return photo_size_list.index(size_type) 
    
    def _name_photo(self, likes_list, photos_list):
        out_list = []
        for photo in photos_list:
            if likes_list.count(int(photo['likes'])) == 1:
                out_list.append({
                    'file_name': str(photo['likes']) + '.jpg', 
                    'size': photo['size'],
                    'url': photo['url']                
                })
            else:
                out_list.append({
                    'file_name': str(photo['likes']) + '_' 
                    + (datetime.datetime.fromtimestamp(int(photo['date'])))
                    .strftime('%Y-%m-%d_%H-%M-%S') + '.jpg', 
                    'size': photo['size'],
                    'url': photo['url']                
                })  
        return out_list              
        
    def get_profile_photos(self):
        params = self._get_common_params()            
        response = requests.get(f'{self.api_url}/photos.get',
                                params=params)        
        if response.ok:            
            try:                 
                photos_list_in = response.json()['response']['items']
                photos_list_out = []  
                photo_size_list = [] 
                likes_list = []            
                for photo in photos_list_in:
                    photo_size_list.clear() 
                    for size in photo['sizes']:
                        photo_size_list.append(size['type']) 
                        index = self._max_size(photo_size_list)
                    photos_list_out.append({
                        'likes': photo['likes']['count'],
                        'date': photo['date'],
                        'size': photo['sizes'][index]['type'],
                        'url': photo['sizes'][index]['url']
                    })
                    likes_list.append(photo['likes']['count'])                               
                return self._name_photo(likes_list, photos_list_out) 
            except Exception:
                logging.critical('invalid user id or VK token')

class YandexDisk:
    
    yandex_url = 'https://cloud-api.yandex.net/v1/disk/resources'
    def __init__(self, yandex_token):
        self.token = yandex_token
        self.params = {'path': 'Photo_from_VK'}
        self.headers = {'Authorization': f'OAuth {self.token}'}
    
    def checking_for_folder_availability(self):         
        params = {
            'path': 'Photo_from_VK',
            'fields': '_embedded.items.name'          
        }     
        name_list = []  
        response = requests.get(self.yandex_url,
                                headers=self.headers,
                                params=params) 
        if response.status_code == 200:
            for name in response.json()['_embedded']['items']:
                name_list.append(name['name']) 
        else:
            if response.status_code == 401:
                logging.critical('incorrect Yandex token') 
                name_list = ['error']  
            else:
                if (response.status_code != 409
                    and response.status_code != 404):
                    logging.critical(f'{response.status_code} error ' \
                                     'viewing folder on Yandex Disk')
                    name_list = ['error']                                     
        return name_list
    
    def create_folder(self):
        response = requests.put(self.yandex_url,
                                headers=self.headers,
                                params=self.params)
        return response
    
    def image_upload(self, file_name, url_download):      
        response = requests.post(f'{self.yandex_url}/upload',
                                 headers=self.headers,
                                 params={'url': url_download,
                                'path': f'Photo_from_VK/{file_name}'})        
        return response
    
    def json_upload(self, json_file, file_name):
        response = requests.get(
            f'{self.yandex_url}/upload',
            headers=self.headers,
            params={'path': f'Photo_from_VK/{file_name}',
                'overwrite' : 'true'}
        )        
        if response.ok:
            url_upload = response.json()['href']             
            response = requests.put(url_upload,
                                    files={'file': json_file})
            return response  
        
    def status_upload(self, url):
        response = requests.get(url, headers=self.headers)
        return response     
    
def save_to_disk(names_already_saved_list, photo_vk_all_list, yd):
    sum = 0
    target_names_list = []
    json_list = []
    for photo_name in photo_vk_all_list:
        if photo_name['file_name'] not in names_already_saved_list:
            if sum < 5: 
                sum += 1 
                target_names_list.append({
                    'file_name': photo_name['file_name'], 
                    'url': photo_name['url'],
                    'size': photo_name['size'] 
                    }) 
        else:
            json_list.append({'file_name': photo_name['file_name'],
                              'size': photo_name['size']})
    attempt = 0   
    while target_names_list and attempt < 10:
        attempt += 1
        for target_name in target_names_list:
            try:
                response = yd.image_upload(target_name['file_name'],
                                           target_name['url'])                             
                response = yd.status_upload(response.json()['href'])  
            except Exception:
                logging.critical(f'{target_name['file_name']} ' \
                                 'error when saving photo')
                exit() 
                  
            if response.json()['status'] != 'failed':                     
                json_list.append({'file_name': target_name['file_name'],
                                  'size': target_name['size']}) 
                logging.info(f'{target_name['file_name']} file is loaded')
                target_names_list.remove(target_name)  
    if target_names_list:
        for not_uploaded_photo in target_names_list:
            logging.error(f'{not_uploaded_photo['file_name']} ' \
                          'failed to load, please try again later')    
    return {'json_list': json_list, 'sum': sum} 

def saving_to_disk(yandex_token, access_token, user_id):  
    try: 
        if not requests.get('https://ya.ru').ok:
            logging.critical('no internet connection') 
            exit()   
    except Exception:
        logging.critical('no internet connection') 
        exit()  
    try:   
        vk = VK(access_token, user_id)
        photo_vk_all_list = vk.get_profile_photos()    
        if photo_vk_all_list:        
            yd = YandexDisk(yandex_token)
            try:
                names_already_saved_list = (
                    yd.checking_for_folder_availability()) 
            except Exception:
                logging.critical('error connecting to Yandex Disk') 
                exit()
               
            if names_already_saved_list != ['error']:
                if names_already_saved_list:  
                    saving_result = save_to_disk(names_already_saved_list,
                                                 photo_vk_all_list, yd)  
                else:            
                    yd.create_folder()  
                    logging.info('Photo_from_VK folder created')  
                    saving_result = save_to_disk(names_already_saved_list,
                                                 photo_vk_all_list, yd)   
                if saving_result['sum'] < 5:
                    logging.info('all user photos are already saved') 
                if saving_result['json_list'] and saving_result['sum'] != 0:            
                    yd.json_upload(json.dumps(saving_result['json_list'],
                                              ensure_ascii=False,
                                              indent=4), 'photo_info.json') 
                    logging.info('photo_info.json file is loaded') 
    except Exception:
        logging.critical('the program terminated unexpectedly') 
        
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s') 
    print('enter your Yandex token')
    yandex_token = input()
    print('enter your VK token')
    access_token = input()
    print('enter your VK user id')
    user_id = input() 
    
    saving_to_disk(yandex_token, access_token, user_id)