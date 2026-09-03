import { useState, useEffect } from 'react';
import { fetchGroups, fetchDirections } from '../../../api/groups';

export const useGroups = () => {
    const [groups, setGroups] = useState([]);
    const [directions, setDirections] = useState([]);
    const [loading, setLoading] = useState(true);
    
    const [pagination, setPagination] = useState({
        count: 0,
        page: 1,
        pageSize: 15,
    });
    
    const [filters, setFilters] = useState({
        status: 'in_progress,completed', // Показываем активные и завершенные
        direction: 'all',
        year: new Date().getFullYear().toString(),
        search: '',
    });

    // Загрузка направлений (один раз при монтировании)
    useEffect(() => {
        fetchDirections()
            .then(res => setDirections(res.data))
            .catch(err => console.error('Ошибка загрузки направлений:', err));
    }, []);

    // Загрузка групп при изменении фильтров или страницы
    useEffect(() => {
        setLoading(true);
        fetchGroups({
            ...filters,
            page: pagination.page,
            pageSize: pagination.pageSize,
        })
            .then(res => {
                setGroups(res.data.results);
                setPagination(prev => ({
                    ...prev,
                    count: res.data.count,
                    total_pages: res.data.total_pages,
                }));
            })
            .catch(err => console.error('Ошибка загрузки групп:', err))
            .finally(() => setLoading(false));
    }, [filters, pagination.page]); // Зависимость от фильтров и страницы

    // Функция обновления фильтра (сбрасывает страницу на 1)
    const updateFilter = (key, value) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPagination(prev => ({ ...prev, page: 1 }));
    };

    const goToPage = (page) => {
        setPagination(prev => ({ ...prev, page }));
    };

    return {
        groups,
        directions,
        loading,
        filters,
        pagination,
        updateFilter,
        goToPage,
    };
};