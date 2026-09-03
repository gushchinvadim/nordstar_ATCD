import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchModules, fetchStaff, fetchStudents, fetchLocations, createGroup } from '../../api/groups';
import styles from './CreateGroup.module.css';

const CreateGroup = () => {
    const navigate = useNavigate();
    
    // Справочники
    const [modules, setModules] = useState([]);
    const [staff, setStaff] = useState([]);
    const [students, setStudents] = useState([]);
    const [locations, setLocations] = useState([]);
    
    // Основная информация
    const [serialNumber, setSerialNumber] = useState('');
    const [application, setApplication] = useState('');
    const [moduleId, setModuleId] = useState('');
    const [status, setStatus] = useState('enrolling');
    
    // Время и место
    const [locationId, setLocationId] = useState('');
    const [startDate, setStartDate] = useState('');
    const [startFaceToFace, setStartFaceToFace] = useState('');
    const [endDate, setEndDate] = useState('');
    const [isSdo, setIsSdo] = useState(false);
    const [startTimeDefault, setStartTimeDefault] = useState('09:00');
    
    // Преподавательский состав
    const [mentorId, setMentorId] = useState('');
    const [curatorId, setCuratorId] = useState('');
    const [directorId, setDirectorId] = useState('');
    
    // Приказ о зачислении
    const [orderInDate, setOrderInDate] = useState('');
    
    // Назначения
    const [enrollments, setEnrollments] = useState([
        { student_id: '', number_in_group: 1, status: 'enrolled' }
    ]);
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Загрузка справочников
    useEffect(() => {
        const loadData = async () => {
            try {
                const [modulesRes, staffRes, studentsRes, locationsRes] = await Promise.all([
                    fetchModules(),
                    fetchStaff(),
                    fetchStudents(),
                    fetchLocations(),
                ]);
                
                setModules(modulesRes.data);
                setStaff(staffRes.data);
                setStudents(studentsRes.data);
                setLocations(locationsRes.data);
            } catch (err) {
                console.error('Ошибка загрузки справочников:', err);
                setError('Не удалось загрузить справочники');
            }
        };
        
        loadData();
    }, []);

    // Автоматическая генерация номера группы
    const assignedNumber = serialNumber && application ? `${serialNumber}-${application}` : '';
   const orderInNumber = assignedNumber ? `${assignedNumber}-З` : '';
    // Добавление назначения
    const addEnrollment = () => {
        setEnrollments([
            ...enrollments,
            { student_id: '', number_in_group: enrollments.length + 1, status: 'enrolled' }
        ]);
    };

    // Удаление назначения
    const removeEnrollment = (index) => {
        const updated = enrollments.filter((_, i) => i !== index);
        setEnrollments(updated.map((e, i) => ({ ...e, number_in_group: i + 1 })));
    };

    // Обновление назначения
    const updateEnrollment = (index, field, value) => {
        const updated = [...enrollments];
        updated[index][field] = value;
        setEnrollments(updated);
    };

    // Отправка формы
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        
        const data = {
            serial_number: serialNumber,
            application: application,
            module_id: moduleId,
            status: status,
            location_id: locationId || null,
            start_date: startDate,
            start_face_to_face: startFaceToFace || null,
            end_date: endDate || null,
            is_sdo: isSdo,
            start_time_default: startTimeDefault,
            mentor_id: mentorId || null,
            curator_id: curatorId || null,
            director_id: directorId || null,
            order_in_date: orderInDate || null,
            enrollments: enrollments.filter(e => e.student_id), // Только заполненные
        };
        
        try {
            const res = await createGroup(data);
            if (res.data.success) {
                alert(`✅ Группа ${res.data.assigned_number} успешно создана!`);
                navigate('/'); // Возврат на дашборд
            } else {
                setError(res.data.error || 'Ошибка создания группы');
            }
        } catch (err) {
            setError(err.response?.data?.error || 'Ошибка сети');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.container}>
            <h1>Создание новой группы</h1>
            
            {error && <div className={styles.error}>{error}</div>}
            
            <form onSubmit={handleSubmit}>
                {/* ОСНОВНАЯ ИНФОРМАЦИЯ */}
                <section className={styles.section}>
                    <h2>Основная информация</h2>
                    
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Номер группы по реестру *</label>
                            <input
                                type="text"
                                value={serialNumber}
                                onChange={(e) => setSerialNumber(e.target.value)}
                                placeholder="001.2026"
                                required
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Номер заявки *</label>
                            <input
                                type="text"
                                value={application}
                                onChange={(e) => setApplication(e.target.value)}
                                placeholder="СЗ/28-001"
                                required
                            />
                        </div>
                    </div>
                    
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Номер группы (автоматически)</label>
                            <input
                                type="text"
                                value={assignedNumber}
                                readOnly
                                className={styles.readonly}
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Номер приказа о зачислении (автоматически)</label>
                            <input
                                type="text"
                                value={orderInNumber}
                                readOnly
                                className={styles.readonly}
                            />
                        </div>
                    </div>
                    
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Дата приказа о зачислении</label>
                            <input
                                type="date"
                                value={orderInDate}
                                onChange={(e) => setOrderInDate(e.target.value)}
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Модуль *</label>
                            <select
                                value={moduleId}
                                onChange={(e) => setModuleId(e.target.value)}
                                required
                            >
                                <option value="">— Выберите модуль —</option>
                                {modules.map(m => (
                                    <option key={m.id} value={m.id}>
                                        {m.code} - {m.title}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    
                    <div className={styles.field}>
                        <label>Статус *</label>
                        <select
                            value={status}
                            onChange={(e) => setStatus(e.target.value)}
                            required
                        >
                            <option value="draft">Черновик</option>
                            <option value="enrolling">Набор</option>
                            <option value="in_progress">Обучение</option>
                            <option value="completed">Завершена</option>
                        </select>
                    </div>
                </section>
                
                {/* ВРЕМЯ И МЕСТО */}
                <section className={styles.section}>
                    <h2>Время и место</h2>
                    
                    <div className={styles.field}>
                        <label>Место проведения</label>
                        <select
                            value={locationId}
                            onChange={(e) => setLocationId(e.target.value)}
                        >
                            <option value="">— Не выбрано —</option>
                            {locations.map(loc => (
                                <option key={loc.id} value={loc.id}>{loc.title}</option>
                            ))}
                        </select>
                    </div>
                    
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Дата начала СДО *</label>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                required
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Дата начала очных занятий</label>
                            <input
                                type="date"
                                value={startFaceToFace}
                                onChange={(e) => setStartFaceToFace(e.target.value)}
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Плановая дата окончания</label>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                            />
                        </div>
                    </div>
                    
                    <div className={styles.row}>
                        <div className={styles.checkbox}>
                            <input
                                type="checkbox"
                                id="isSdo"
                                checked={isSdo}
                                onChange={(e) => setIsSdo(e.target.checked)}
                            />
                            <label htmlFor="isSdo">Только СДО (без очных занятий)</label>
                        </div>
                        
                        <div className={styles.field}>
                            <label>Время начала очных занятий</label>
                            <input
                                type="time"
                                value={startTimeDefault}
                                onChange={(e) => setStartTimeDefault(e.target.value)}
                            />
                        </div>
                    </div>
                </section>
                
                {/* ПРЕПОДАВАТЕЛЬСКИЙ СОСТАВ */}
                <section className={styles.section}>
                    <h2>Преподавательский состав</h2>
                    
                    <div className={styles.field}>
                        <label>Наставник группы</label>
                        <select
                            value={mentorId}
                            onChange={(e) => setMentorId(e.target.value)}
                        >
                            <option value="">— Не выбран —</option>
                            {staff.map(s => (
                                <option key={s.id} value={s.id}>{s.full_name}</option>
                            ))}
                        </select>
                    </div>
                    
                    <div className={styles.field}>
                        <label>Специалист 1 категории (Куратор)</label>
                        <select
                            value={curatorId}
                            onChange={(e) => setCuratorId(e.target.value)}
                        >
                            <option value="">— Не выбран —</option>
                            {staff.map(s => (
                                <option key={s.id} value={s.id}>{s.full_name}</option>
                            ))}
                        </select>
                    </div>
                    
                    <div className={styles.field}>
                        <label>Подписывающий руководитель</label>
                        <select
                            value={directorId}
                            onChange={(e) => setDirectorId(e.target.value)}
                        >
                            <option value="">— Не выбран —</option>
                            {staff.map(s => (
                                <option key={s.id} value={s.id}>{s.full_name}</option>
                            ))}
                        </select>
                    </div>
                </section>
                
                {/* НАЗНАЧЕНИЯ */}
                <section className={styles.section}>
                    <h2>Назначения (Слушатели)</h2>
                    
                    {enrollments.map((enrollment, index) => (
                        <div key={index} className={styles.enrollmentRow}>
                            <div className={styles.field}>
                                <label>Слушатель *</label>
                                <select
                                    value={enrollment.student_id}
                                    onChange={(e) => updateEnrollment(index, 'student_id', e.target.value)}
                                    required
                                >
                                    <option value="">— Выберите слушателя —</option>
                                    {students.map(s => (
                                        <option key={s.id} value={s.id}>
                                            {s.full_name} ({s.profession})
                                        </option>
                                    ))}
                                </select>
                            </div>
                            
                            <div className={styles.fieldSmall}>
                                <label>№ в группе</label>
                                <input
                                    type="number"
                                    value={enrollment.number_in_group}
                                    onChange={(e) => updateEnrollment(index, 'number_in_group', parseInt(e.target.value))}
                                    min="1"
                                    required
                                />
                            </div>
                            
                            <div className={styles.field}>
                                <label>Статус</label>
                                <select
                                    value={enrollment.status}
                                    onChange={(e) => updateEnrollment(index, 'status', e.target.value)}
                                >
                                    <option value="enrolled">Зачислен</option>
                                    <option value="in_progress">Обучается</option>
                                    <option value="completed">Завершен</option>
                                    <option value="dismissed">Отчислен</option>
                                </select>
                            </div>
                            
                            {enrollments.length > 1 && (
                                <button
                                    type="button"
                                    onClick={() => removeEnrollment(index)}
                                    className={styles.removeBtn}
                                >
                                    ✕
                                </button>
                            )}
                        </div>
                    ))}
                    
                    <button type="button" onClick={addEnrollment} className={styles.addBtn}>
                        + Добавить слушателя
                    </button>
                </section>
                
                {/* КНОПКИ */}
                <div className={styles.actions}>
                    <button type="submit" className={styles.submitBtn} disabled={loading}>
                        {loading ? 'Создание...' : 'Создать группу'}
                    </button>
                    <button type="button" onClick={() => navigate('/')} className={styles.cancelBtn}>
                        Отмена
                    </button>
                </div>
            </form>
        </div>
    );
};

export default CreateGroup;