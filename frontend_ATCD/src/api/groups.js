// src/api/groups.js
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
    
    // ИЗМЕНЕНО: убрали /docs
    return api.get(`/api/docs/groups/?${params.toString()}`);
};

export const fetchDirections = () => {
    // ИЗМЕНЕНО: убрали /docs
    return api.get('/api/docs/directions/');
};

// Справочники (ИЗМЕНЕНО: убрали /docs)
export const fetchModules = () => api.get('/api/docs/modules/');
export const fetchStaff = () => api.get('/api/docs/staff/');
export const fetchStudents = () => api.get('/api/docs/students/');
export const fetchLocations = () => api.get('/api/docs/locations/');

// Создание группы (ИЗМЕНЕНО: убрали /docs)
export const createGroup = (data) => api.post('/api/docs/groups/create/', data);

// Получение данных группы для редактирования (ИЗМЕНЕНО: убрали /docs)
export const fetchGroupDetail = (groupId) => api.get(`/api/docs/group/${groupId}/edit/`);

// Обновление группы (ИЗМЕНЕНО: убрали /docs)
export const updateGroup = (groupId, data) => api.patch(`/api/docs/group/${groupId}/update/`, data);

// Генерация расписания (ИЗМЕНЕНО: убрали /docs)
export const generateSchedule = (groupId) => api.post(`/api/docs/group/${groupId}/generate-schedule/`);