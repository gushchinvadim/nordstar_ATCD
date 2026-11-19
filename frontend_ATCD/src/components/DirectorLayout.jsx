import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import Layout from './Layout';

const menuItems = [
    {
        path: '/director/dashboard',
        label: 'Расписания для утверждения',
        icon: '▦',
    },
    { path: '/director/cancelled', label: 'Отменённые заявки', icon: '⊘' },
    {
        path: '/director/statistics/auc',
        label: 'Статистика АУЦ',
        icon: '▥',
    },
    {
        path: '/director/statistics/ministry',
        label: 'Статистика для Минобра',
        icon: '▤',
    },
];

export default function DirectorLayout() {
    const { user } = useContext(AuthContext);
    const allowed =
        user?.is_director ||
        user?.roles?.is_director ||
        user?.roles?.is_superuser;
    if (!allowed)
        return (
            <p role="alert" style={{ padding: 24 }}>
                Кабинет доступен директору. Переключите роль или обратитесь к
                администратору.
            </p>
        );
    return <Layout sidebarItems={menuItems} />;
}
