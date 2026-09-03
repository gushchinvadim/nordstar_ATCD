import { Navigate, Outlet } from 'react-router-dom';
import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';

const ProtectedRoute = () => {
    const { user, loading } = useContext(AuthContext);

    if (loading) return <div style={{ padding: 20 }}>Загрузка системы...</div>;
    
    // Если юзера нет — редирект на логин
    if (!user) return <Navigate to="/login" replace />;

    // Если юзер есть — рендерим вложенные маршруты (Outlet)
    return <Outlet />;
};

export default ProtectedRoute;