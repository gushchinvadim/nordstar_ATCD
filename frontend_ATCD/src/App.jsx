import EditStudent from './pages/methodist/EditStudent';
import GroupFunding from './pages/methodist/GroupFunding';
import Instructors from './pages/methodist/Instructors';
// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

import MaintenancePage from './pages/MaintenancePage';
import Landing from './pages/Landing'; 
import LoginPage from './pages/LoginPage';
import QuickStart from './pages/QuickStart';

import Layout from './components/Layout';
import InstructorLayout from './components/InstructorLayout';
import DirectorLayout from './components/DirectorLayout';
import StudentLayout from './components/StudentLayout';

// Методист
import Dashboard from './pages/methodist/Dashboard';
import CreateGroup from './pages/methodist/CreateGroup'; // Универсальная форма
import GroupDocuments from './pages/methodist/GroupDocuments';
import GroupGrades from './pages/methodist/GroupGrades';
import GroupDocumentsDetail from './pages/methodist/GroupDocumentsDetail';
import ScheduleEditor from './pages/methodist/ScheduleEditor';
import CreateStudent from './pages/methodist/CreateStudent';

// Инструктор
import InstructorDashboard from './pages/instructor/Dashboard';
import InstructorGrades from './pages/instructor/Grades';

// Студент
import StudentDashboard from './pages/student/Dashboard';

// Директор
import DirectorDashboard from './pages/director/Dashboard';
import CancelledRequests from './pages/director/CancelledRequests';
import MinistryStatistics from './pages/director/MinistryStatistics';
import AUCStatistics from './pages/director/AUCStatistics';

function App() {
    const isMaintenance = import.meta.env.VITE_IS_MAINTENANCE === 'true';

    if (isMaintenance) {
        return <MaintenancePage />;
    }

    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Landing />} /> 
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/quick-start" element={<QuickStart />} /> 
                    
                    <Route element={<ProtectedRoute />}>
                        {/* === МЕТОДИСТ === */}
                        <Route element={<Layout />}>
                            <Route path="/methodist" element={<Navigate to="/groups" replace />} />
                            <Route path="/groups" element={<GroupDocuments />} />
                            
                            {/* 🔥 Один компонент для создания И редактирования */}
                            <Route path="/create-group" element={<CreateGroup />} />
                            <Route path="/groups/:groupId/edit" element={<CreateGroup />} />
                            
                            <Route path="/create-student" element={<CreateStudent />} />
                            <Route path="/edit-student" element={<EditStudent />} />
                            <Route path="/instructors" element={<Instructors />} />
                            <Route path="/groups/:groupId/funding" element={<GroupFunding />} />
                            <Route path="/groups/:groupId/grades" element={<GroupGrades />} />
                            <Route path="/groups/:groupId/documents" element={<GroupDocumentsDetail />} />
                            <Route path="/groups/:groupId/schedule" element={<ScheduleEditor />} />
                        </Route>

                        {/* === ИНСТРУКТОР === */}
                        <Route element={<InstructorLayout />}>
                            <Route path="/instructor/dashboard" element={<InstructorDashboard />} />
                            <Route path="/instructor/grades/:groupId" element={<InstructorGrades />} />
                        </Route>

                        {/* === ДИРЕКТОР === */}
                        <Route element={<DirectorLayout />}>
                            <Route path="/director/dashboard" element={<DirectorDashboard />} />
                            <Route path="/director/cancelled" element={<CancelledRequests />} />
                            <Route path="/director/statistics" element={<Navigate to="/director/statistics/auc" replace />} />
                            <Route path="/director/statistics/auc" element={<AUCStatistics />} />
                            <Route path="/director/statistics/ministry" element={<MinistryStatistics />} />
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