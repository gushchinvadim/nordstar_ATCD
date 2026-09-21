// src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Landing from './pages/Landing'; 

// Общая страница
import LoginPage from './pages/LoginPage';

// Layouts
import Layout from './components/Layout';
import InstructorLayout from './components/InstructorLayout';

// Методист
import Dashboard from './pages/methodist/Dashboard';
import CreateGroup from './pages/methodist/CreateGroup';
import GroupDocuments from './pages/methodist/GroupDocuments';
import EditGroup from './pages/methodist/EditGroup';

// Инструктор
import InstructorDashboard from './pages/instructor/Dashboard';
import InstructorGrades from './pages/instructor/Grades';

// Студент (НОВОЕ)
import StudentDashboard from './pages/student/Dashboard';
import StudentLayout from './components/StudentLayout';

// Директор
import DirectorLayout from './components/DirectorLayout';
import DirectorDashboard from './pages/director/Dashboard';

function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    {/* 1. Публичный маршрут: ГЛАВНАЯ СТРАНИЦА (Лендинг) */}
                    <Route path="/" element={<Landing />} /> 
                    <Route path="/login" element={<LoginPage />} />
                    
                    {/* 2. Защищенные маршруты (требуют авторизации) */}
                    <Route element={<ProtectedRoute />}>
                        
                        {/* === МЕТОДИСТ === */}
                        <Route element={<Layout />}>
                            <Route path="/methodist" element={<Dashboard />} /> {/* <-- ИЗМЕНИТЬ ЗДЕСЬ */}
                            <Route path="/groups" element={<GroupDocuments />} />
                            <Route path="/create-group" element={<CreateGroup />} />
                            <Route path="/groups/:groupId/edit" element={<EditGroup />} />
                        </Route>

                        {/* === ИНСТРУКТОР === */}
                        <Route element={<InstructorLayout />}>
                            <Route path="/instructor/dashboard" element={<InstructorDashboard />} />
                            <Route path="/instructor/grades/:groupId" element={<InstructorGrades />} />
                        </Route>

                        {/* === ДИРЕКТОР === */}
                        <Route element={<DirectorLayout />}>
                            <Route path="/director/dashboard" element={<DirectorDashboard />} />
                        </Route>

                        {/* === СТУДЕНТ === */}
                        <Route element={<StudentLayout />}>
                            <Route path="/student/dashboard" element={<StudentDashboard />} />
                        </Route>
                        
                    </Route>
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}
export default App;