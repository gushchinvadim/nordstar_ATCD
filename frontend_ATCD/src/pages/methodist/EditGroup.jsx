import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchGroupDetail, updateGroup, fetchModules, fetchStaff, fetchStudents, fetchLocations } from '../../api/groups';
import styles from './EditGroup.module.css';

const EditGroup = () => {
    const { groupId } = useParams();
    const navigate = useNavigate();
    
    // Справочники
    const [modules, setModules] = useState([]);
    const [staff, setStaff] = useState([]);
    const [students, setStudents] = useState([]);
    const [locations, setLocations] = useState([]);
    
    // Данные группы (инициализируем безопасными значениями)
    const [formData, setFormData] = useState({
        assigned_number: '',
        serial_number: '',
        application: '',
        module_id: '',
        status: 'enrolling',
        location_id: '',
        start_date: '',
        start_face_to_face: '',
        end_date: '',
        is_sdo: false,
        start_time_default: '09:00',
        mentor_id: '',
        curator_id: '',
        director_id: '',
        order_in_date: '',
        enrollments: [],
    });
    
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    // Загрузка справочников и данных группы
    useEffect(() => {
        const loadData = async () => {
            try {
                const [modulesRes, staffRes, studentsRes, locationsRes, groupRes] = await Promise.all([
                    fetchModules(),
                    fetchStaff(),
                    fetchStudents(),
                    fetchLocations(),
                    fetchGroupDetail(groupId),
                ]);
                
                setModules(modulesRes.data);
                setStaff(staffRes.data);
                setStudents(studentsRes.data);
                setLocations(locationsRes.data);
                
                // БЕЗОПАСНОЕ присвоение данных с явными fallback-значениями
                const data = groupRes.data;
                setFormData({
                    assigned_number: data.assigned_number || '',
                    serial_number: data.serial_number || '',
                    application: data.application || '',
                    module_id: data.module_id || '',
                    status: data.status || 'enrolling',
                    location_id: data.location_id || '',
                    start_date: data.start_date || '',
                    start_face_to_face: data.start_face_to_face || '',
                    end_date: data.end_date || '',
                    is_sdo: Boolean(data.is_sdo),
                    start_time_default: data.start_time_default || '09:00',
                    mentor_id: data.mentor_id || '',
                    curator_id: data.curator_id || '',
                    director_id: data.director_id || '',
                    order_in_date: data.order_in_date || '',
                    enrollments: Array.isArray(data.enrollments) ? data.enrollments : [], // ГАРАНТИЯ МАССИВА
                });
                
            } catch (err) {
                console.error('Ошибка загрузки:', err);
                setError('Не удалось загрузить данные группы. Проверьте консоль и Network.');
            } finally {
                setLoading(false);
            }
        };
        
        loadData();
    }, [groupId]);

    // Автоматическая генерация номеров
    const assignedNumber = formData.serial_number && formData.application 
        ? `${formData.serial_number}-${formData.application}` 
        : formData.assigned_number; // fallback на то, что пришло с бэка
        
    const orderInNumber = assignedNumber ? `${assignedNumber}-З` : '';

    // Обновление полей формы
    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    // Добавление назначения
    const addEnrollment = () => {
        setFormData(prev => ({
            ...prev,
            enrollments: [
                ...prev.enrollments,
                { student_id: '', number_in_group: prev.enrollments.length + 1, status: 'enrolled' }
            ]
        }));
    };

    // Удаление назначения
    const removeEnrollment = (index) => {
        setFormData(prev => ({
            ...prev,
            enrollments: prev.enrollments.filter((_, i) => i !== index)
                .map((e, i) => ({ ...e, number_in_group: i + 1 }))
        }));
    };

    // Обновление назначения
    const updateEnrollment = (index, field, value) => {
        setFormData(prev => {
            const updated = [...prev.enrollments];
            updated[index] = { ...updated[index], [field]: value };
            return { ...prev, enrollments: updated };
        });
    };

    // Отправка формы
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setSaving(true);
        
        try {
            const res = await updateGroup(groupId, formData);
            if (res.data.success) {
                setSuccess(res.data.message);
                setTimeout(() => navigate('/groups'), 2000);
            }
        } catch (err) {
            console.error('Ошибка сохранения:', err);
            setError(err.response?.data?.error || 'Ошибка сохранения данных');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className={styles.loading}>Загрузка данных группы...</div>;
    }

    return (
        <div className={styles.container}>
            <h1>Редактирование группы: {formData.assigned_number || 'Новая группа'}</h1>
            
            {error && <div className={styles.error}>{error}</div>}
            {success && <div className={styles.success}>{success}</div>}
            
            <form onSubmit={handleSubmit}>
                {/* ОСНОВНАЯ ИНФОРМАЦИЯ */}
                <section className={styles.section}>
                    <h2>Основная информация</h2>
                    
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Номер группы по реестру *</label>
                            <input
                                type="text"
                                value={formData.serial_number}
                                onChange={(e) => handleChange('serial_number', e.target.value)}
                                placeholder="001.2026"
                                required
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Номер заявки *</label>
                            <input
                                type="text"
                                value={formData.application}
                                onChange={(e) => handleChange('application', e.target.value)}
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
                                value={formData.order_in_date}
                                onChange={(e) => handleChange('order_in_date', e.target.value)}
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Модуль *</label>
                            <select
                                value={formData.module_id}
                                onChange={(e) => handleChange('module_id', e.target.value)}
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
                            value={formData.status}
                            onChange={(e) => handleChange('status', e.target.value)}
                            required
                        >
                            <option value="draft">Черновик</option>
                            <option value="enrolling">Набор</option>
                            <option value="in_progress">Обучение</option>
                            <option value="completed">Завершена</option>
                            <option value="archived">Архив</option>
                        </select>
                    </div>
                </section>
                
                {/* ВРЕМЯ И МЕСТО */}
                <section className={styles.section}>
                    <h2>Время и место</h2>
                    
                    <div className={styles.field}>
                        <label>Место проведения</label>
                        <select
                            value={formData.location_id}
                            onChange={(e) => handleChange('location_id', e.target.value)}
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
                                value={formData.start_date}
                                onChange={(e) => handleChange('start_date', e.target.value)}
                                required
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Дата начала очных занятий</label>
                            <input
                                type="date"
                                value={formData.start_face_to_face}
                                onChange={(e) => handleChange('start_face_to_face', e.target.value)}
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label>Плановая дата окончания</label>
                            <input
                                type="date"
                                value={formData.end_date}
                                onChange={(e) => handleChange('end_date', e.target.value)}
                            />
                        </div>
                    </div>
                    
                    <div className={styles.row}>
                        <div className={styles.checkbox}>
                            <input
                                type="checkbox"
                                id="isSdo"
                                checked={formData.is_sdo}
                                onChange={(e) => handleChange('is_sdo', e.target.checked)}
                            />
                            <label htmlFor="isSdo">Только СДО (без очных занятий)</label>
                        </div>
                        
                        <div className={styles.field}>
                            <label>Время начала очных занятий</label>
                            <input
                                type="time"
                                value={formData.start_time_default}
                                onChange={(e) => handleChange('start_time_default', e.target.value)}
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
                            value={formData.mentor_id}
                            onChange={(e) => handleChange('mentor_id', e.target.value)}
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
                            value={formData.curator_id}
                            onChange={(e) => handleChange('curator_id', e.target.value)}
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
                            value={formData.director_id}
                            onChange={(e) => handleChange('director_id', e.target.value)}
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
                    
                    {/* ГАРАНТИРОВАННЫЙ МАССИВ */}
                    {(formData.enrollments || []).map((enrollment, index) => (
                        <div key={enrollment.id || index} className={styles.enrollmentRow}>
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
                                    onChange={(e) => updateEnrollment(index, 'number_in_group', parseInt(e.target.value) || 1)}
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
                            
                            {(formData.enrollments?.length || 0) > 1 && (
                                <button
                                    type="button"
                                    onClick={() => removeEnrollment(index)}
                                    className={styles.removeBtn}
                                    title="Удалить слушателя"
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
                    <button type="submit" className={styles.submitBtn} disabled={saving}>
                        {saving ? 'Сохранение...' : 'Сохранить изменения'}
                    </button>
                    <button type="button" onClick={() => navigate('/groups')} className={styles.cancelBtn}>
                        Отмена
                    </button>
                </div>
            </form>
        </div>
    );
};

export default EditGroup;