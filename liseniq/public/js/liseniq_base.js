let notificationTimeout;
// Variable para controlar el intervalo de actualización automática
let notificationInterval; 

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('app-sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');
    const closeBtn = document.getElementById('sidebar-close-btn');
    const overlay = document.getElementById('sidebar-overlay');

    const measurementModal = document.getElementById('create-measurement-modal');
    const openModalBtn = document.getElementById('btn-open-create-measurement-modal');
    const closeModalBtn = document.getElementById('btn-close-measurement-modal');
    const createBlankMeasurementBtn = document.getElementById('btn-blank-measurement');
    const openTemplatestBtn = document.getElementById('btn-template-measurement');

    function toggleSidebar() {
        if (sidebar && overlay) {
            sidebar.classList.toggle('sidebar-visible');
            overlay.classList.toggle('active');
        }
    }

    function openMeasurementModal() {
        if (measurementModal) measurementModal.classList.remove('d-none');
    }

    function closeMeasurementModal() {
        if (measurementModal) measurementModal.classList.add('d-none');
    }

    if (toggleBtn) toggleBtn.addEventListener('click', toggleSidebar);
    if (closeBtn) closeBtn.addEventListener('click', toggleSidebar);
    if (overlay) overlay.addEventListener('click', toggleSidebar);

    if (openModalBtn) openModalBtn.addEventListener('click', openMeasurementModal);
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeMeasurementModal);
    if (measurementModal) {
        measurementModal.addEventListener('click', (e) => {
            if (e.target === measurementModal) {
                closeMeasurementModal();
            }
        });
    }

    if (createBlankMeasurementBtn) {
        createBlankMeasurementBtn.addEventListener('click', () => {
            window.location.href = '/measurement/new_measurement';
        });
    }

     if (openTemplatestBtn) {
        openTemplatestBtn.addEventListener('click', () => {
            window.location.href = '/iq-templates';
        });
    }

    fetch('/api/method/liseniq.utils.login_util.get_user_company_name')
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                const companyDiv = document.getElementById('iq-header-company-name');
                if (companyDiv) {
                    companyDiv.textContent = data.message;
                }
            }
        });

    const avatar = document.getElementById('iq-header-avatar');
    const userMenu = document.getElementById('iq-header-user-menu');
    const logoutBtn = document.getElementById('iq-header-logout');
    const sidebarLogoutLink = document.getElementById('sidebar-logout-link');
    const accessDeniedBtn = document.getElementById('btn-access-denied-logout');

    if (avatar && userMenu) {
        avatar.addEventListener('click', function(e) {
            e.stopPropagation();
            userMenu.classList.toggle('d-none');
            const notifDropdown = document.getElementById('notification-dropdown');
            if(notifDropdown) notifDropdown.classList.add('d-none');
        });

        document.addEventListener('click', function(e) {
            if (!userMenu.classList.contains('d-none') && !avatar.contains(e.target) && !userMenu.contains(e.target)) {
                userMenu.classList.add('d-none');
            }
        });
    }

    // Manejo seguro del logout (limpieza de sesión y redirección)
    const handleLogout = function(e) {
        if(e) e.preventDefault();
        
        localStorage.clear();
        sessionStorage.clear();

        fetch('/api/method/logout', { 
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        })
        .then(() => {
            window.location.replace('/');
        })
        .catch((err) => {
            console.error('Error durante logout:', err);
            window.location.replace('/');
        });
    };

    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    if (sidebarLogoutLink) {
        sidebarLogoutLink.addEventListener('click', handleLogout);
    }

    if (accessDeniedBtn) {
        accessDeniedBtn.addEventListener('click', handleLogout);
    }

    // Inicializar lógica de notificaciones
    initNotifications();
    
    // Inicializar lógica de onboarding
    initOnboarding();
});

function initOnboarding() {
    // Modal de Bienvenida
    const modal = document.getElementById('welcomeModal');
    const btnOpen = document.getElementById('btn-open-welcome');
    const btnClose = document.getElementById('closeWelcomeModal');
    const btnDecline = document.getElementById('btnDeclineModal');
    const btnTakeTour = document.getElementById('btnTakeTour');

    // Función para abrir el modal
    function openModal() {
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden'; // Evitar scroll del body
        }
    }

    // Función para cerrar el modal
    function closeModal() {
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = ''; // Restaurar scroll del body
        }
    }

    const driver = window.driver.js.driver;
    const driverObj = driver({
        showProgress: false,
        onDestroyed: function() {
          frappe.call('liseniq.utils.login_util.set_first_login_false')    
        },
        nextBtnText: 'Siguiente',
        prevBtnText: 'Anterior',
        closeBtnText: 'Cerrar',
        doneBtnText: 'Listo',
        steps: [
            { element: '#home-sec', popover: { title: 'Inicio', description: 'Aquí podrás visualizar todas las mediciones que haz creado, su estado y crear nuevas.', side: "left", align: 'start' }},
            { element: '#templates-sec', popover: { title: 'Plantillas', description: 'Aquí podrás crear y visualizar las plantillas de preguntas para crear nuevas mediciones.', side: "bottom", align: 'start' }},
            { element: '#results-sec', popover: { title: 'Resultados', description: 'Aquí podrás ver los resultados de las mediciones que hayas realizado.', side: "bottom", align: 'start' }},
            { element: '#contacts-sec', popover: { title: 'Contactos', description: 'Aquí podrás cargar o importar los contactos que participarán en tus mediciones. Puedes hacerlo manualmente o  por carga masiva', side: "left", align: 'start' }},
            { popover: { title: 'Has terminado el tour', description: 'Ahora puedes comenzar a usar la plataforma.' } }
        ]
    });

    if (btnOpen) {
        btnOpen.addEventListener('click', function() {
            if (driverObj) {
                driverObj.drive();
            }
        });
    }

    // Cerrar modal con el botón X
    if (btnClose) {
        btnClose.addEventListener('click', closeModal);
    }

    // Cerrar modal con el botón "Ahora no"
    if (btnDecline) {
        btnDecline.addEventListener('click', closeModal);
    }

    // Cerrar modal al hacer clic fuera del contenido
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    // Cerrar modal con la tecla Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
            closeModal();
        }
    });

    // Botón "Tomar el tour" - iniciar el recorrido
    if (btnTakeTour) {
        btnTakeTour.addEventListener('click', function() {
            closeModal();
            // Iniciar el tour con driver.js
            if (driverObj) {
                driverObj.drive();
            }
        });
    }

    const firstLoginInput = document.getElementById('firstLogin');
    console.log('Valor de firstLogin:', firstLoginInput ? firstLoginInput.value : 'Elemento no encontrado');
    if (firstLoginInput && firstLoginInput.value === true) {
        openModal();
    }
}

function initNotifications() {
    const btnNotifications = document.getElementById('btn-notifications');
    const notificationDropdown = document.getElementById('notification-dropdown');

    // 1. Carga inicial
    checkNewNotifications();

    // 2. Configurar intervalo para buscar notificaciones cada 60 segundos
    if (notificationInterval) clearInterval(notificationInterval);
    notificationInterval = setInterval(checkNewNotifications, 30000);

    // 3. Event Listener para abrir/cerrar dropdown
    if (btnNotifications && notificationDropdown) {
        btnNotifications.addEventListener('click', function(e) {
            e.stopPropagation();
            // Cerrar menú de usuario si está abierto
            const userMenu = document.getElementById('iq-header-user-menu');
            if(userMenu) userMenu.classList.add('d-none');

            notificationDropdown.classList.toggle('d-none');
            
            // Si abrimos el menú, forzamos una carga de la lista para asegurar que esté actualizada
            if (!notificationDropdown.classList.contains('d-none')) {
                loadNotificationsList();
            }
        });

        // 4. Cerrar al hacer clic fuera
        document.addEventListener('click', function(e) {
            if (!notificationDropdown.classList.contains('d-none') && 
                !btnNotifications.contains(e.target) && 
                !notificationDropdown.contains(e.target)) {
                notificationDropdown.classList.add('d-none');
            }
        });
    }
}

async function checkNewNotifications() {
    try {

        const countResponse = await fetch('/api/method/liseniq.utils.api_notification.get_unread_notification_count');
        const countData = await countResponse.json();
        const unreadCount = countData.message || 0;

        // Actualizar el indicador visual (Badge)
        updateBadgeUI(unreadCount);

        if (unreadCount > 0) {
            loadNotificationsList();
        } else {
            showEmptyNotificationState();
        }

    } catch (error) {
        console.error('Error verificando nuevas notificaciones:', error);
    }
}

function updateBadgeUI(count) {
    const badge = document.getElementById('notification-badge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }
}

function showEmptyNotificationState() {
    const listContainer = document.getElementById('notification-list');
    if (listContainer) {
        listContainer.innerHTML = `
            <div class="text-center p-4 text-muted">
                <small>No tienes notificaciones nuevas</small>
            </div>`;
    }
}

function loadNotificationsList() {
    const listContainer = document.getElementById('notification-list');
    if (!listContainer) return;

    // Solo mostrar loading si la lista está vacía actualmente
    if (listContainer.children.length === 0 || listContainer.innerText.includes('No tienes notificaciones')) {
        listContainer.innerHTML = '<div class="text-center p-3 text-muted"><i class="fa fa-spinner fa-spin"></i> Cargando...</div>';
    }

    fetch('/api/method/liseniq.utils.api_notification.get_unread_notifications')
        .then(response => response.json())
        .then(data => {
            const notifications = data.message || [];
            
            if (notifications.length === 0) {
                showEmptyNotificationState();
                return;
            }

            listContainer.innerHTML = ''; // Limpiar loader
            notifications.forEach(notif => {
                const item = document.createElement('div');
                item.className = 'notification-item';
                item.id = `notif-${notif.name}`;
                item.innerHTML = `
                    <div class="notification-content">
                        <span class="notification-title">${notif.pn_title}</span>
                        <span class="notification-message">${notif.pn_message}</span>
                    </div>
                    <div class="notification-action" onclick="markAsRead('${notif.name}')" title="Marcar como leída">
                        <i class="fa fa-trash-o" style="color: #E95E5E;"></i>
                    </div>
                `;
                listContainer.appendChild(item);
            });
        })
        .catch(err => {
            console.error('Error loading notifications list:', err);
            listContainer.innerHTML = '<div class="text-center p-3 text-danger"><small>Error al cargar</small></div>';
        });
}

// Función global para marcar como leída
window.markAsRead = function(notificationName) {
    const item = document.getElementById(`notif-${notificationName}`);
    if (item) {
        item.style.opacity = '0.5';
    }

    fetch(`/api/method/liseniq.utils.api_notification.mark_notification_as_read?notification_name=${encodeURIComponent(notificationName)}`)
        .then(response => response.json())
        .then(data => {
            if (data.message && data.message.status === 'success') {
                if (item) {
                    item.remove();
                    // Si ya no quedan elementos en la lista visual, mostrar mensaje vacío
                    const listContainer = document.getElementById('notification-list');
                    if (listContainer && listContainer.children.length === 0) {
                        showEmptyNotificationState();
                    }
                }
                // Actualizar el conteo general nuevamente
                checkNewNotifications();
                showGlobalNotification('Notificación marcada como leída', 'success', 3000);
            } else {
                showGlobalNotification('Error al eliminar notificación', 'error');
                if (item) item.style.opacity = '1';
            }
        })
        .catch(err => {
            console.error('Error marking as read:', err);
            showGlobalNotification('Error de conexión', 'error');
            if (item) item.style.opacity = '1';
        });
};

function showGlobalNotification(message, type, duration = 5000) {
    const notificationBar = document.getElementById('global-notification-bar');
    const notificationMessage = document.getElementById('global-notification-message');

    if (!notificationBar || !notificationMessage) {
        console.error('Elementos de la barra de notificación no encontrados en el DOM.');
        return;
    }

    clearTimeout(notificationTimeout);
    notificationMessage.textContent = message;
    notificationBar.classList.remove('notification-success', 'notification-error');
    if (type === 'success') {
        notificationBar.classList.add('notification-success');
    } else if (type === 'error') {
        notificationBar.classList.add('notification-error');
    }

    notificationBar.classList.add('show');
    notificationTimeout = setTimeout(() => {
        notificationBar.classList.remove('show');
    }, duration);
}