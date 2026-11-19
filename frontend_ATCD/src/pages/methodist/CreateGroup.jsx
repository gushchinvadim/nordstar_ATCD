// src/pages/methodist/CreateGroup.jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchModules, fetchStaff, fetchStudents, fetchLocations } from '../../api/groups';
import api from '../../api/config'; // Добавлено для PATCH запроса
import styles from './CreateGroup.module.css';
import FundingFields from '../../components/FundingFields';
import { emptyFunding } from '../../components/fundingUtils';

const CreateGroup = () => {
    const { groupId } = useParams(); // Получаем ID, если мы в режиме редактирования
    const navigate = useNavigate();
    const isEditMode = !!groupId; // Флаг: true, если редактируем
    
    // Справочники
    const [modules, setModules] = useState([]);
    const [staff, setStaff] = useState([]);
    const [students, setStudents] = useState([]);
    const [locations, setLocations] = useState([]);
    
    const [fundingReferences, setFundingReferences] = useState(null);
    const [fundingDefaults, setFundingDefaults] = useState(emptyFunding);
    const [fundingReason, setFundingReason] = useState('');
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
    const [isFetching, setIsFetching] = useState(true);

    // Загрузка справочников и данных группы (если редактирование)
    useEffect(() => {
        const loadData = async () => {
            try {
                const [modulesRes, staffRes, studentsRes, locationsRes, fundingRes] = await Promise.all([
                    fetchModules(),
                    fetchStaff(),
                    fetchStudents(),
                    fetchLocations(),
                    api.get('/api/execution/methodist/funding/references/').catch(() => ({ data: null })),
                ]);
                
                setModules(modulesRes.data);
                setStaff(staffRes.data);
                setStudents(studentsRes.data);
                setLocations(locationsRes.data);
                setFundingReferences(fundingRes.data);

                // 🔥 ЕСЛИ РЕДАКТИРОВАНИЕ: загружаем данные группы
                if (isEditMode) {
                    const groupRes = await api.get(`/api/docs/group/${groupId}/edit/`);
                    const data = groupRes.data;
                    
                    setSerialNumber(data.serial_number || '');
                    setApplication(data.application || '');
                    setModuleId(data.module_id || '');
                    setStatus(data.status || 'enrolling');
                    setLocationId(data.location_id || '');
                    setStartDate(data.start_date || '');
                    setStartFaceToFace(data.start_face_to_face || '');
                    setEndDate(data.end_date || '');
                    setIsSdo(data.is_sdo || false);
                    setStartTimeDefault(data.start_time_default || '09:00');
                    setMentorId(data.mentor_id || '');
                    setCuratorId(data.curator_id || '');
                    setDirectorId(data.director_id || '');
                    setOrderInDate(data.order_in_date || '');
                    setEnrollments(data.enrollments && data.enrollments.length > 0 ? data.enrollments : [{ student_id: '', number_in_group: 1, status: 'enrolled' }]);
                }
            } catch (err) {
                console.error('Ошибка загрузки данных:', err);
                setError('Не удалось загрузить данные');
            } finally {
                setIsFetching(false);
            }
        };
        
        loadData();
    }, [groupId, isEditMode]);

    const assignedNumber = serialNumber && application ? `${serialNumber}-${application}` : '';
    const orderInNumber = assignedNumber ? `${assignedNumber}-З` : '';

    const addEnrollment = () => {
        setEnrollments([
            ...enrollments,
            { student_id: '', number_in_group: enrollments.length + 1, status: 'enrolled' }
        ]);
    };

    const removeEnrollment = (index) => {
        const updated = enrollments.filter((_, i) => i !== index);
        setEnrollments(updated.map((e, i) => ({ ...e, number_in_group: i + 1 })));
    };

    const updateEnrollment = (index, field, value) => {
        const updated = [...enrollments];
        updated[index][field] = value;
        setEnrollments(updated);
    };

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
            funding_defaults: fundingDefaults,
            funding_reason: fundingReason,
            enrollments: enrollments.filter(e => e.student_id).map((row) => ({ ...fundingDefaults, ...row })),
        };
        
        try {
            // 🔥 Выбираем URL и метод в зависимости от режима
            const url = isEditMode ? `/api/docs/group/${groupId}/update/` : '/api/docs/groups/create/';
            const method = isEditMode ? 'patch' : 'post';
            
            const res = await api[method](url, data);
            
            if (res.data.success) {
                alert(`✅ Группа ${isEditMode ? 'успешно обновлена' : ` ${res.data.assigned_number} успешно создана`}!`);
                navigate(isEditMode ? `/groups/${groupId}/documents` : '/groups');
            } else {
                setError(res.data.error || 'Ошибка сохранения группы');
            }
        } catch (err) {
            setError(err.response?.data?.error || 'Ошибка сети');
        } finally {
            setLoading(false);
        }
    };

    if (isFetching) return <div className={styles.loading}>Загрузка формы...</div>;

    return (
        <div className={styles.container}>
            <h1>{isEditMode ? '✏️ Редактирование группы' : '➕ Создание новой группы'}</h1>
            
            {error && <div className={styles.error}>{error}</div>}
            
            <form onSubmit={handleSubmit}>
                {/* ОСНОВНАЯ ИНФОРМАЦИЯ */}
                <section className={styles.section}>
                    <h2>Основная информация</h2>
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Номер группы по реестру *</label>
                            <input type="text" value={serialNumber} onChange={(e) => setSerialNumber(e.target.value)} placeholder="001.2026" required />
                        </div>
                        <div className={styles.field}>
                            <label>Номер заявки *</label>
                            <input type="text" value={application} onChange={(e) => setApplication(e.target.value)} placeholder="СЗ/28-001" required />
                        </div>
                    </div>
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Номер группы (автоматически)</label>
                            <input type="text" value={assignedNumber} readOnly className={styles.readonly} />
                        </div>
                        <div className={styles.field}>
                            <label>Номер приказа о зачислении (автоматически)</label>
                            <input type="text" value={orderInNumber} readOnly className={styles.readonly} />
                        </div>
                    </div>
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Дата приказа о зачислении</label>
                            <input type="date" value={orderInDate} onChange={(e) => setOrderInDate(e.target.value)} />
                        </div>
                        <div className={styles.field}>
                            <label>Модуль *</label>
                            <select value={moduleId} onChange={(e) => setModuleId(e.target.value)} required>
                                <option value="">— Выберите модуль —</option>
                                {modules.map(m => (<option key={m.id} value={m.id}>{m.code} - {m.title}</option>))}
                            </select>
                        </div>
                    </div>
                    <div className={styles.field}>
                        <label>Статус *</label>
                        <select value={status} onChange={(e) => setStatus(e.target.value)} required>
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
                        <select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
                            <option value="">— Не выбрано —</option>
                            {locations.map(loc => (<option key={loc.id} value={loc.id}>{loc.title}</option>))}
                        </select>
                    </div>
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label>Дата начала СДО *</label>
                            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
                        </div>
                        <div className={styles.field}>
                            <label>Дата начала очных занятий</label>
                            <input type="date" value={startFaceToFace} onChange={(e) => setStartFaceToFace(e.target.value)} />
                        </div>
                        <div className={styles.field}>
                            <label>Плановая дата окончания</label>
                            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                        </div>
                    </div>
                    <div className={styles.row}>
                        <div className={styles.checkbox}>
                            <input type="checkbox" id="isSdo" checked={isSdo} onChange={(e) => setIsSdo(e.target.checked)} />
                            <label htmlFor="isSdo">Только СДО (без очных занятий)</label>
                        </div>
                        <div className={styles.field}>
                            <label>Время начала очных занятий</label>
                            <input type="time" value={startTimeDefault} onChange={(e) => setStartTimeDefault(e.target.value)} />
                        </div>
                    </div>
                </section>
                
                {/* ПРЕПОДАВАТЕЛЬСКИЙ СОСТАВ */}
                <section className={styles.section}>
                    <h2>Преподавательский состав</h2>
                    <div className={styles.field}>
                        <label>Наставник группы</label>
                        <select value={mentorId} onChange={(e) => setMentorId(e.target.value)}>
                            <option value="">— Не выбран —</option>
                            {staff.map(s => (<option key={s.id} value={s.id}>{s.full_name}</option>))}
                        </select>
                    </div>
                    <div className={styles.field}>
                        <label>Специалист 1 категории (Куратор)</label>
                        <select value={curatorId} onChange={(e) => setCuratorId(e.target.value)}>
                            <option value="">— Не выбран —</option>
                            {staff.map(s => (<option key={s.id} value={s.id}>{s.full_name}</option>))}
                        </select>
                    </div>
                    <div className={styles.field}>
                        <label>Подписывающий руководитель</label>
                        <select value={directorId} onChange={(e) => setDirectorId(e.target.value)}>
                            <option value="">— Не выбран —</option>
                            {staff.map(s => (<option key={s.id} value={s.id}>{s.full_name}</option>))}
                        </select>
                    </div>
                </section>
                
                {/* НАЗНАЧЕНИЯ */}
                <section className={styles.section}>
                    <h2>Назначения (Слушатели)</h2>
                    {fundingReferences && <>
                        <h3>Общий источник финансирования</h3>
                        <FundingFields value={fundingDefaults} references={fundingReferences} onChange={setFundingDefaults} disabled={loading} />
                        <button type="button" className={styles.addBtn} disabled={loading} onClick={() => setEnrollments((previous) => previous.map((row) => ({ ...row, ...fundingDefaults })))}>Применить ко всем слушателям</button>
                        <p>Общий вариант используется для новых назначений. Для существующих слушателей примените его явно или выберите источник отдельно.</p>
                        {isEditMode && <label>Причина изменения финансирования (для завершённого обучения)<textarea value={fundingReason} maxLength={2000} onChange={(e) => setFundingReason(e.target.value)} /></label>}
                    </>}
                    {enrollments.map((enrollment, index) => (
                        <div key={index} className={styles.enrollmentRow}>
                            <div className={styles.field}>
                                <label>Слушатель *</label>
                                <select value={enrollment.student_id} onChange={(e) => updateEnrollment(index, 'student_id', e.target.value)} required>
                                    <option value="">— Выберите слушателя —</option>
                                    {students.map(s => (<option key={s.id} value={s.id}>{s.full_name} ({s.profession})</option>))}
                                </select>
                            </div>
                            <div className={styles.fieldSmall}>
                                <label>№ в группе</label>
                                <input type="number" value={enrollment.number_in_group} onChange={(e) => updateEnrollment(index, 'number_in_group', parseInt(e.target.value))} min="1" required />
                            </div>
                            <div className={styles.field}>
                                <label>Статус</label>
                                <select value={enrollment.status} onChange={(e) => updateEnrollment(index, 'status', e.target.value)}>
                                    <option value="enrolled">Зачислен</option>
                                    <option value="in_progress">Обучается</option>
                                    <option value="completed">Завершен</option>
                                    <option value="dismissed">Отчислен</option>
                                </select>
                            </div>
                            {fundingReferences && <FundingFields value={{ ...fundingDefaults, ...Object.fromEntries(Object.entries(enrollment).filter(([key]) => ['funding_source', 'payer_organization', 'funding_reference'].includes(key))) }} references={fundingReferences} disabled={loading} onChange={(value) => setEnrollments((previous) => previous.map((row, current) => current === index ? { ...row, ...value } : row))} />}
                            {enrollments.length > 1 && (
                                <button type="button" onClick={() => removeEnrollment(index)} className={styles.removeBtn}>✕</button>
                            )}
                        </div>
                    ))}
                    <button type="button" onClick={addEnrollment} className={styles.addBtn}>+ Добавить слушателя</button>
                </section>
                
                {/* КНОПКИ */}
                <div className={styles.actions}>
                    <button type="submit" className={styles.submitBtn} disabled={loading}>
                        {loading ? 'Сохранение...' : (isEditMode ? '💾 Сохранить изменения' : '✅ Создать группу')}
                    </button>
                    <button type="button" onClick={() => navigate(isEditMode ? `/groups/${groupId}/documents` : '/groups')} className={styles.cancelBtn}>
                        Отмена
                    </button>
                </div>
            </form>
        </div>
    );
};

export default CreateGroup;