// src/pages/student/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import styles from './Dashboard.module.css';
import api from '../../api/config';

const StudentDashboard = () => {
    const [modules, setModules] = useState([]);
    const [expandedModule, setExpandedModule] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchModules();
    }, []);

    const fetchModules = async () => {
        try {
            const response = await api.get('/api/execution/student/modules/');
            const activeModules = response.data.filter(module => !module.is_fully_completed);
            setModules(activeModules);
            setLoading(false);
        } catch (err) {
            console.error("Ошибка загрузки:", err);
            setError('Ошибка загрузки данных');
            setLoading(false);
        }
    };

    const handleConfirm = async (actionType, params = {}) => {
        try {
            await api.post('/api/execution/student/confirm/', {
                action_type: actionType,
                ...params
            });
            await fetchModules(); 
            alert('Действие успешно подтверждено!');
        } catch (err) {
            alert(err.response?.data?.error || 'Ошибка подтверждения');
        }
    };

    const toggleModule = (moduleId) => {
        setExpandedModule(expandedModule === moduleId ? null : moduleId);
    };

    if (loading) return <div className={styles.loading}>Загрузка...</div>;
    if (error) return <div className={styles.error}>{error}</div>;

    // Хелпер для проверки, является ли модуль АСП (Суша или Вода)
    const isAspModule = (module) => {
        // 1. Проверяем явный тип модуля (если бэкенд когда-нибудь его добавит)
        if (module.module_type === 'asp-l' || module.module_type === 'asp-w') return true;
        
        // 2. Проверяем код модуля
        if (module.module_code?.toUpperCase().includes('ASP')) return true;
        
        // 3. ГЛАВНАЯ ПРОВЕРКА: ищем в расписании занятие с session_type 'asp-l' или 'asp-w'
        if (module.schedule && Array.isArray(module.schedule)) {
            return module.schedule.some(item => 
                item.session_type === 'asp-l' || item.session_type === 'asp-w'
            );
        }
        
        return false;
    };

    return (
        <div className={styles.container}>
            <h1 className={styles.mainTitle}>Личный кабинет слушателя</h1>
            <h2 className={styles.subtitle}>Текущие модули обучения</h2>
            
            {modules.length === 0 ? (
                <div className={styles.emptyState}>
                    <p>🎉 У вас нет активных заданий. Все модули успешно завершены!</p>
                </div>
            ) : (
                modules.map(module => (
                    <div key={module.enrollment_id} className={styles.moduleCard}>
                        <div className={styles.moduleHeader} onClick={() => toggleModule(module.module_id)}>
                            <div className={styles.moduleInfo}>
                                <h3>{module.module_title}</h3>
                                <span className={styles.moduleCode}>{module.module_code}</span>
                            </div>
                            <div className={styles.moduleMeta}>
                                <p className={styles.groupNumber}>Группа: {module.group_number}</p>
                                <p className={styles.status}>Статус: {module.db_status}</p>
                            </div>
                            <button className={styles.expandButton}>
                                {expandedModule === module.module_id ? '▲ Свернуть' : '▼ Открыть блок подписей'}
                            </button>
                        </div>

                        {expandedModule === module.module_id && (
                            <div className={styles.signaturesBlock}>
                                
                                {/* 1. Ознакомление с расписанием */}
                                <div className={styles.signatureSection}>
                                    <h4>1. Ознакомление с учебным расписанием</h4>
                                    <a href={module.schedule_doc?.url || '#'} target="_blank" rel="noopener noreferrer" className={styles.docLink}>
                                        📄 Открыть документ с расписанием
                                    </a>
                                    {module.schedule_doc?.has_ack ? (
                                        <div className={styles.confirmed}>✅ Ознакомлен {new Date(module.schedule_doc.ack_date).toLocaleString('ru-RU')}</div>
                                    ) : (
                                        <button className={styles.actionButton} onClick={() => handleConfirm('student_schedule_ack', { enrollment_id: module.enrollment_id })}>
                                            ✅ Я ознакомлен с расписанием и согласен с ним
                                        </button>
                                    )}
                                </div>

                                {/* 2. Инструктаж по ТБ */}
                                <div className={styles.signatureSection}>
                                    <h4>2. Инструктаж по ОТ, ТБ, ППБ + согласие на обработку ПД + ознакомление с порядком</h4>
                                    <a href={module.instructing_doc?.url || '#'} target="_blank" rel="noopener noreferrer" className={styles.docLink}>
                                        📄 Открыть документ с инструктажем
                                    </a>
                                    {module.instructing_doc?.has_ack ? (
                                        <div className={styles.confirmed}>✅ Ознакомлен {new Date(module.instructing_doc.ack_date).toLocaleString('ru-RU')}</div>
                                    ) : (
                                        <button className={styles.actionButton} onClick={() => handleConfirm('student_safety_ack', { enrollment_id: module.enrollment_id })}>
                                            ✅ Ознакомлен и согласен
                                        </button>
                                    )}
                                </div>

                                {/* 3. Отметка о посещаемости */}
                                <div className={styles.signatureSection}>
                                    <h4>3. Отметка о посещаемости</h4>
                                    {module.schedule?.length === 0 ? (
                                        <p className={styles.pending}>Занятия еще не запланированы</p>
                                    ) : (
                                        <div className={styles.attendanceList}>
                                            {module.schedule.map(item => {
                                                const isSdo = item.session_type === 'sdo';
                                                return (
                                                    <div key={item.id} className={styles.attendanceItem}>
                                                        <div className={styles.attendanceInfo}>
                                                            <span className={styles.date}>{item.date}</span>
                                                            <span className={styles.time}>{item.start_time} - {item.end_time}</span>
                                                            <span className={styles.section}>{item.section_title}</span>
                                                            {item.subsection_title && <span className={styles.subsection}>({item.subsection_title})</span>}
                                                            {isSdo && <span className={styles.sdoBadge}>СДО</span>}
                                                        </div>
                                                        {isSdo ? (
                                                            <span className={styles.sdoText}>Посещение не фиксируется</span>
                                                        ) : item.has_attendance ? (
                                                            <span className={styles.attended}>✅ Присутствовал</span>
                                                        ) : (
                                                            <button className={styles.smallButton} onClick={() => handleConfirm('student_attendance_confirmed', { schedule_item_id: item.id })}>
                                                                Подтвердить присутствие
                                                            </button>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>

                                {/* 4. Промежуточные оценки */}
                                <div className={styles.signatureSection}>
                                    <h4>4. Результаты промежуточной оценки знаний</h4>
                                    {module.grades?.filter(g => !g.is_final).length === 0 ? (
                                        <p className={styles.pending}>Оценки еще не выставлены</p>
                                    ) : (
                                        module.grades.filter(g => !g.is_final).map(grade => (
                                            <div key={grade.id} className={styles.gradeItem}>
                                                <div className={styles.gradeInfo}>
                                                    <span className={styles.sectionTitle}>{grade.section_title}</span>
                                                    <span className={`${styles.score} ${grade.passed ? styles.passed : styles.failed}`}>
                                                        {grade.score !== null 
                                                            ? (grade.grade_type === 'binary' 
                                                                ? (grade.score == 1 ? 'Зачет' : 'Не зачет') 
                                                                : grade.score) 
                                                            : '—'}
                                                    </span>
                                                    <span className={styles.status}>{grade.passed ? 'Сдано' : 'Не сдано'}</span>
                                                </div>
                                                {grade.has_grade_ack ? (
                                                    <span className={styles.acknowledged}>✅ Ознакомлен</span>
                                                ) : (
                                                    <button className={styles.smallButton} onClick={() => handleConfirm('student_grade_ack', { assessment_id: grade.id })}>
                                                        С оценкой ознакомлен и согласен
                                                    </button>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>

                                {/* 5. Итоговая аттестация */}
                                <div className={styles.signatureSection}>
                                    <h4>5. Итоговая аттестация (экзамен)</h4>
                                    {module.grades?.filter(g => g.is_final).length === 0 ? (
                                        <p className={styles.pending}>Экзамен еще не проведен</p>
                                    ) : (
                                        module.grades.filter(g => g.is_final).map(grade => (
                                            <div key={grade.id} className={styles.gradeItem}>
                                                <div className={styles.gradeInfo}>
                                                    <span className={styles.sectionTitle}>{grade.section_title}</span>
                                                    <span className={`${styles.score} ${grade.passed ? styles.passed : styles.failed}`}>
                                                        {grade.score !== null 
                                                            ? (grade.grade_type === 'binary' 
                                                                ? (grade.score == 1 ? 'Зачет' : 'Не зачет') 
                                                                : grade.score) 
                                                            : '—'}
                                                    </span>
                                                    <span className={styles.status}>{grade.passed ? 'Сдано' : 'Не сдано'}</span>
                                                </div>
                                                {grade.has_grade_ack ? (
                                                    <span className={styles.acknowledged}>✅ Ознакомлен</span>
                                                ) : (
                                                    <button className={styles.smallButton} onClick={() => handleConfirm('student_grade_ack', { assessment_id: grade.id })}>
                                                        С оценкой ознакомлен и согласен
                                                    </button>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>

                                {/* 6. Получение документа (ОБЪЕДИНЕННЫЙ БЛОК: Свидетельство + ЗНТ) */}
<div className={styles.signatureSection}>
    <h4>6. Получение документа об обучении и Задания на тренировку (ЗНТ)</h4>
    
    {(() => {
        const allGradesSet = module.all_grades_set || false;
        const isAsp = isAspModule(module);
        const hasCertificates = module.certificates?.length > 0;
        
        // Модуль готов к выдаче документов, если:
        // - Есть сертификаты (для обычных модулей)
        // - ИЛИ это АСП-модуль со всеми выставленными оценками
        const moduleReady = hasCertificates || (isAsp && allGradesSet);
        
        // Если модуль не готов — показываем заглушку
        if (!moduleReady) {
            return (
                <p className={styles.pending}>
                    📋 Документы будут доступны после завершения модуля (выставления всех оценок)
                </p>
            );
        }
        
        return (
            <div className={styles.documentsList}>
                {/* 6.1. Сертификаты / Свидетельства */}
                {module.certificates?.map(cert => (
                    <div key={cert.id} className={styles.certificateItem}>
                        <div className={styles.certificateInfo}>
                            <span className={styles.certType}>{cert.type}</span>
                            <span className={styles.certNumber}>№ {cert.number}</span>
                            {cert.issue_date && <span className={styles.certDate}>от {cert.issue_date}</span>}
                        </div>
                        {cert.has_received ? (
                            <span className={styles.received}>✅ Получил</span>
                        ) : (
                            <button 
                                className={styles.smallButton} 
                                onClick={() => handleConfirm('certificate_received', { certificate_id: cert.id, enrollment_id: module.enrollment_id })}
                            >
                                Получил документ
                            </button>
                        )}
                    </div>
                ))}

                {/* 6.2. ЗНТ — показываем ТОЛЬКО для АСП и ТОЛЬКО если все оценки выставлены */}
                {isAsp && allGradesSet && (
                    <div className={styles.certificateItem}>
                        <div className={styles.certificateInfo}>
                            <span className={styles.certType}>Задание на тренировку (ЗНТ)</span>
                            <span className={styles.certNumber}>Б/Н</span>
                            {module.znt_issue_date && <span className={styles.certDate}>от {module.znt_issue_date}</span>}
                        </div>
                        {module.znt_received ? (
                            <span className={styles.received}>✅ ЗНТ получен</span>
                        ) : (
                            <button 
                                className={styles.smallButton} 
                                onClick={() => handleConfirm('znt_received', { enrollment_id: module.enrollment_id })}
                            >
                                Получил ЗНТ
                            </button>
                        )}
                    </div>
                )}
            </div>
        );
    })()}
</div>

                            </div>
                        )}
                    </div>
                ))
            )}
        </div>
    );
};

export default StudentDashboard;