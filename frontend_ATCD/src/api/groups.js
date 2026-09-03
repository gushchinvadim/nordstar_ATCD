import api from './config';

export const fetchGroups = (filters = {}) => {
    const params = new URLSearchParams();
    
    if (filters.status) params.append('status', filters.status);
    if (filters.direction && filters.direction !== 'all') {
        params.append('direction', filters.direction);
    }
    if (filters.year) params.append('year', filters.year);
    if (filters.search) params.append('search', filters.search);
    if (filters.page) params.append('page', filters.page);
    if (filters.pageSize) params.append('page_size', filters.pageSize);
    
    return api.get(`/docs/api/groups/?${params.toString()}`);
};

export const fetchDirections = () => {
    return api.get('/docs/api/directions/');
};


// Справочники
export const fetchModules = () => api.get('/docs/api/modules/');
export const fetchStaff = () => api.get('/docs/api/staff/');
export const fetchStudents = () => api.get('/docs/api/students/');
export const fetchLocations = () => api.get('/docs/api/locations/');

// Создание группы
export const createGroup = (data) => api.post('/docs/api/groups/create/', data);

// Получение данных группы для редактирования
export const fetchGroupDetail = (groupId) => api.get(`/docs/api/group/${groupId}/edit/`);

// Обновление группы
export const updateGroup = (groupId, data) => api.patch(`/docs/api/group/${groupId}/update/`, data);
// Генерация расписания
export const generateSchedule = (groupId) => api.post(`/docs/api/group/${groupId}/generate-schedule/`);