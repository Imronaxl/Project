// === Инициализация языка из cookie ===
function getCurrentLanguage() {
    const match = document.cookie.match(/(?:^|; )language=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : 'russian';
}

// === Сохранение языка в cookie ===
function setLanguageCookie(lang) {
    document.cookie = `language=${lang}; path=/; max-age=31536000`; // 1 год
}
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// === Функция установки логина в меню ===
function setLoginInMenu() {
    // Пробуем получить логин из разных возможных кук
    const login = getCookie('login') || getCookie('saved_name') || getCookie('user_login');
    
    if (login) {
        const profileTextElement = document.getElementById('menuProfileText');
        if (profileTextElement) {
            profileTextElement.textContent = login;
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Функция для получения значения куки по имени
    function getCookie(name) {
        const cookies = document.cookie.split(';');
        for(let cookie of cookies) {
            const [key, value] = cookie.trim().split('=');
            if(key === name) {
                return decodeURIComponent(value);
            }
        }
        return null;
    }
    setLoginInMenu();

    // Получаем логин из куки (предполагается, что кука называется 'saved_name')
    const userLogin = getCookie('saved_name');
    
    // Если логин получен, обновляем ссылку
    if(userLogin) {
        const profileLinks = document.querySelectorAll('#floatingMenuContent a[href^="profile?login="]');
        
        profileLinks.forEach(link => {
            // Обновляем href, сохраняя все остальные параметры если они есть
            const url = new URL(link.href);
            url.searchParams.set('login', userLogin);
            link.href = url.toString();
        });
    } else {
        console.log('Логин пользователя не найден в куках');
    }
    const menuButton = document.getElementById('floatingMenuButton');
    const menuContent = document.getElementById('floatingMenuContent');

    if (!menuButton || !menuContent) return;

    // === Состояние меню ===
    let isDragging = false;
    let mouseX = 0, mouseY = 0;
    let menuX = 0, menuY = 0;
    let inactivityTimer = null;

    // === Инициализация позиции из localStorage ===
    function initMenuPosition() {
        const savedPos = localStorage.getItem('floatingMenuPos');
        if (savedPos) {
            [menuX, menuY] = savedPos.split(',').map(Number);
            updateMenuPosition();
        } else {
            menuX = 30;
            menuY = 30;
            savePosition();
        }
    }

    // === Сохранение позиции ===
    function savePosition() {
        localStorage.setItem('floatingMenuPos', `${menuX},${menuY}`);
    }

    // === Прямое позиционирование через left/top ===
    function updateMenuPosition() {
        menuButton.style.left = `${menuX}px`;
        menuButton.style.top = `${menuY}px`;
    }

    // === Таймер неактивности ===
    function resetInactivityTimer() {
        menuButton.classList.remove('transparent');
        clearTimeout(inactivityTimer);
        inactivityTimer = setTimeout(() => {
            menuButton.classList.add('transparent');
            closeMenu();
        }, 6000);
    }

    // === Плавное открытие меню ===
    function openMenu() {
        const btnRect = menuButton.getBoundingClientRect();
        const menuRect = menuContent.getBoundingClientRect();
        const buffer = 8;

        let left = btnRect.right + buffer;
        let top = btnRect.top - 5;

        // Коррекция если не помещается справа
        if (left + menuRect.width > window.innerWidth) {
            left = btnRect.left - menuRect.width - buffer;
        }

        // Коррекция вертикальной позиции
        if (btnRect.bottom + menuRect.height > window.innerHeight) {
            top = Math.max(10, btnRect.top - (menuRect.height - btnRect.height) / 2);
        }

        menuContent.style.left = `${left}px`;
        menuContent.style.top = `${top}px`;
        menuContent.classList.add('open');
        resetInactivityTimer();
    }

    function closeMenu() {
        menuContent.classList.remove('open');
        resetInactivityTimer();
    }

    // === Перетаскивание только ЛКМ ===
    menuButton.addEventListener('mousedown', function(e) {
        if (e.button !== 0) return; // Только левая кнопка
        
        isDragging = true;
        mouseX = e.clientX;
        mouseY = e.clientY;
        
        // Сохраняем текущую позицию
        const rect = menuButton.getBoundingClientRect();
        menuX = rect.left;
        menuY = rect.top;
        
        // Отключаем CSS-анимации для мгновенного перемещения
        menuButton.style.transition = 'none';
        closeMenu();
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        // Прямое вычисление новой позиции
        const dx = e.clientX - mouseX;
        const dy = e.clientY - mouseY;
        
        // Обновляем позицию
        menuX += dx;
        menuY += dy;
        
        // Ограничиваем движение внутри экрана
        const maxX = window.innerWidth - menuButton.offsetWidth;
        const maxY = window.innerHeight - menuButton.offsetHeight;
        
        menuX = Math.max(0, Math.min(maxX, menuX));
        menuY = Math.max(0, Math.min(maxY, menuY));
        
        updateMenuPosition();
        
        // Обновляем позицию курсора для следующего шага
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        
        isDragging = false;
        savePosition(); // Сохраняем новую позицию
        menuButton.style.transition = 'all 0.3s ease'; // Возвращаем анимацию
        resetInactivityTimer();
    });

    // === Обработчики событий ===
    menuButton.addEventListener('click', (e) => {
        if (isDragging) {
            isDragging = false;
            return;
        }
        toggleMenu();
    });

    document.addEventListener('click', (e) => {
        if (!menuButton.contains(e.target) && !menuContent.contains(e.target)) {
            closeMenu();
        }
    });

    // === Таймер активности ===
    const debouncedReset = debounce(resetInactivityTimer, 100);
    ['mousemove', 'keydown', 'click', 'scroll'].forEach(event =>
        document.addEventListener(event, debouncedReset)
    );

    // === Инициализация ===
    initMenuPosition();
    resetInactivityTimer();

    // === Адаптация под размер экрана ===
    window.addEventListener('resize', () => {
        const rect = menuButton.getBoundingClientRect();
        const newX = Math.max(0, Math.min(window.innerWidth - menuButton.offsetWidth, rect.left));
        const newY = Math.max(0, Math.min(window.innerHeight - menuButton.offsetHeight, rect.top));
        menuX = newX;
        menuY = newY;
        updateMenuPosition();
        savePosition();
    });

    // === Вспомогательные функции ===
    function toggleMenu() {
        if (menuContent.classList.contains('open')) {
            closeMenu();
        } else {
            openMenu();
        }
    }

    function debounce(fn, delay) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => fn.apply(this, args), delay);
        };
    }
});