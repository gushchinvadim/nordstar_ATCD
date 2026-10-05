// src/pages/methodist/CreateStudent.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './CreateStudent.module.css';

// Универсальный базовый URL с защитой от отсутствия переменной окружения и лишних слешей
const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

const CreateStudent = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    // Справочники
    const [citizenships, setCitizenships] = useState([]);
    const [aircraftTypes, setAircraftTypes] = useState([]);
    const [professions, setProfessions] = useState([]);

    const [formData, setFormData] = useState({
        surname: '',
        name: '',
        patronymic: '',
        email: '',
        sex: 'M',
        dob: '',
        snils: '',
        name_latin: '',
        surname_latin: '',
        employee_id: '',
        citizenship: '',
        aircraft_type: '',
        profession: '',
        is_active: true,
    });

    // Загрузка справочников при монтировании
    useEffect(() => {
        const token = localStorage.getItem('accessToken');
        
        const fetchReferences = async () => {
            try {
                const headers = { 'Authorization': `Bearer ${token}` };

                // Гражданства
                const citRes = await fetch(`${API_BASE_URL}/api/execution/references/citizenships/`, { headers });
                if (citRes.ok) setCitizenships(await citRes.json());

                // Типы ВС
                const aircraftRes = await fetch(`${API_BASE_URL}/api/execution/references/aircraft_types/`, { headers });
                if (aircraftRes.ok) setAircraftTypes(await aircraftRes.json());

                // Профессии
                const profRes = await fetch(`${API_BASE_URL}/api/execution/references/professions/`, { headers });
                if (profRes.ok) setProfessions(await profRes.json());

            } catch (err) {
                console.error('Ошибка загрузки справочников:', err);
                setError('Не удалось загрузить справочные данные.');
            }
        };

        fetchReferences();
    }, []);

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({ 
            ...prev, 
            [name]: type === 'checkbox' ? checked : value 
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        setSuccess('');

        const token = localStorage.getItem('accessToken');

        // 🔑 Безопасное преобразование ID: если строка пустая, отправляем null, иначе парсим число
        const dataToSend = {
            ...formData,
            citizenship: formData.citizenship ? parseInt(formData.citizenship, 10) : null,
            aircraft_type: formData.aircraft_type ? parseInt(formData.aircraft_type, 10) : null,
            profession: formData.profession ? parseInt(formData.profession, 10) : null,
        };
    
        try {
            const response = await fetch(`${API_BASE_URL}/api/execution/students/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(dataToSend)
            });

            if (response.ok) {
                const result = await response.json();
                setSuccess(result.message || 'Слушатель успешно создан!');
                
                // Очищаем форму после успешного создания
                setFormData({
                    surname: '', name: '', patronymic: '', email: '', sex: 'M',
                    dob: '', snils: '', name_latin: '', surname_latin: '',
                    employee_id: '', citizenship: '', aircraft_type: '', profession: '',
                    is_active: true,
                });
                
                // Опционально: можно раскомментировать строку ниже для авто-перехода через 2 секунды
                // setTimeout(() => navigate('/methodist/students'), 2000);
            } else {
                const errData = await response.json();
                // Пытаемся вытащить первую понятную ошибку из словаря Django
                const firstErrorKey = Object.keys(errData)[0];
                const firstError = errData[firstErrorKey];
                setError(Array.isArray(firstError) ? firstError[0] : 'Ошибка при создании. Проверьте данные.');
            }
        } catch (err) {
            console.error('Network error:', err);
            setError('Ошибка сети. Проверьте подключение или попробуйте позже.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.container}>
            <h1>👤 Создание нового слушателя</h1>
            
            {/* 🔑 ЕДИНЫЙ ТЕГ FORM для всех полей */}
            <form onSubmit={handleSubmit}>
                <div className={styles.section}>
                    <h2>Основные данные</h2>
                    <p className={styles.subtitle}>
                        Заполните данные. Аккаунт для входа будет создан автоматически на основе Email.
                    </p>
                    
                    {error && <div className={styles.error}>{error}</div>}
                    {success && <div className={styles.success}>{success}</div>}

                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Фамилия *</label>
                            <input name="surname" value={formData.surname} onChange={handleChange} required placeholder="Иванов" />
                        </div>
                        <div className={styles.field}>
                            <label>Имя *</label>
                            <input name="name" value={formData.name} onChange={handleChange} required placeholder="Иван" />
                        </div>
                        <div className={styles.field}>
                            <label>Отчество</label>
                            <input name="patronymic" value={formData.patronymic} onChange={handleChange} placeholder="Иванович" />
                        </div>
                    </div>

                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Email (будет логином и паролем) *</label>
                            <input type="email" name="email" value={formData.email} onChange={handleChange} required placeholder="ivanov@nordstar.ru" />
                        </div>
                        <div className={styles.fieldSmall}>
                            <label>Пол</label>
                            <select name="sex" value={formData.sex} onChange={handleChange}>
                                <option value="M">Мужской</option>
                                <option value="F">Женский</option>
                            </select>
                        </div>
                        <div className={styles.field}>
                            <label>Дата рождения</label>
                            <input type="date" name="dob" value={formData.dob} onChange={handleChange} />
                        </div>
                    </div>

                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>СНИЛС</label>
                            <input name="snils" value={formData.snils} onChange={handleChange} placeholder="123-456-789 00" />
                        </div>
                        <div className={styles.field}>
                            <label>Фамилия (латиницей)</label>
                            <input name="surname_latin" value={formData.surname_latin} onChange={handleChange} placeholder="IVANOV" />
                        </div>
                        <div className={styles.field}>
                            <label>Имя (латиницей)</label>
                            <input name="name_latin" value={formData.name_latin} onChange={handleChange} placeholder="IVAN" />
                        </div>
                    </div>

                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>ID сотрудника</label>
                            <input name="employee_id" value={formData.employee_id} onChange={handleChange} placeholder="EMP-123" />
                        </div>
                    </div>
                </div>

                <div className={styles.section}>
                    <h2>Справочные данные</h2>
                    
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Гражданство</label>
                            <select name="citizenship" value={formData.citizenship} onChange={handleChange}>
                                <option value="">-- Не выбрано --</option>
                                {citizenships.map(cit => (
                                    <option key={cit.id} value={cit.id}>{cit.name}</option>
                                ))}
                            </select>
                        </div>
                        <div className={styles.field}>
                            <label>Тип ВС</label>
                            <select name="aircraft_type" value={formData.aircraft_type} onChange={handleChange}>
                                <option value="">-- Не выбрано --</option>
                                {aircraftTypes.map(aircraft => (
                                    <option key={aircraft.id} value={aircraft.id}>{aircraft.name}</option>
                                ))}
                            </select>
                        </div>
                        <div className={styles.field}>
                            <label>Профессия</label>
                            <select name="profession" value={formData.profession} onChange={handleChange}>
                                <option value="">-- Не выбрано --</option>
                                {professions.map(prof => (
                                    <option key={prof.id} value={prof.id}>{prof.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className={styles.checkbox}>
                        <input 
                            type="checkbox" 
                            name="is_active" 
                            id="is_active"
                            checked={formData.is_active} 
                            onChange={handleChange} 
                        />
                        <label htmlFor="is_active">Активен</label>
                    </div>

                    <div className={styles.actions}>
                        <button type="button" className={styles.cancelBtn} onClick={() => navigate('/methodist')} disabled={loading}>
                            Отмена
                        </button>
                        <button type="submit" className={styles.submitBtn} disabled={loading}>
                            {loading ? 'Создание...' : 'Создать слушателя'}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );
};

export default CreateStudent;