import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/methodist/Dashboard';
import CreateGroup from './pages/methodist/CreateGroup';
import GroupDocuments from './pages/methodist/GroupDocuments';
import EditGroup from './pages/methodist/EditGroup';

function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    {/* Публичный маршрут */}
                    <Route path="/login" element={<LoginPage />} />

                    {/* Защищенные маршруты */}
                    <Route element={<ProtectedRoute />}>
                        <Route element={<Layout />}>
                            {/* Главная страница */}
                            <Route path="/" element={<Dashboard />} />
                            <Route path="/groups" element={<GroupDocuments />} />
                            <Route path="/methodist" element={<Dashboard />} />
                            
                            {/* Создание группы */}
                            <Route path="/create-group" element={<CreateGroup />} />
                            {/* Редактирование группы */}
                            <Route path="/groups/:groupId/edit" element={<EditGroup />} />
                            
                            {/* Сюда потом добавим другие страницы */}
                        </Route>
                    </Route>
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}

export default App;