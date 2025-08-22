function logout() {
    fetch(' /logout')
        .then(response => {
            if (response.ok) {
                return response.text();
            } else {
                throw new Error('Ошибка при выполнении запроса');
            }
        })
        .then(data => {
            console.log(data);
            window.location.href = "authorization.html";
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

fetch(' /get_login')
    .then(response => response.json())
    .then(data => {
        const userLogin = document.getElementById('userLogin');
        if (data.login == null) {
            window.location.href = "authorization.html";
        } else {
            userLogin.textContent = data.login;
        }
    })
    .catch(error => {
        userLogin.textContent = "Оффлайн";
    });

function showFullText(newsId) {
    const fullText = document.getElementById(newsId + "Full");
    const showBtn = document.querySelector(`#${newsId}Container .show-btn`);
    const hideBtn = document.querySelector(`#${newsId}Container .hide-btn`);

    fullText.style.display = "block";
    showBtn.style.display = "none";
    hideBtn.style.display = "inline-block";
    fullText.style.maxHeight = fullText.scrollHeight + "px"; // Установка максимальной высоты для показа всего текста
}

function hideFullText(newsId) {
    const fullText = document.getElementById(newsId + "Full");
    const showBtn = document.querySelector(`#${newsId}Container .show-btn`);
    const hideBtn = document.querySelector(`#${newsId}Container .hide-btn`);
    fullText.style.maxHeight = 0; // Установка максимальной высоты 0, чтобы скрыть текст
    fullText.style.display = "none";
    showBtn.style.display = "inline-block";
    hideBtn.style.display = "none";
}



    function showLanguagePopup() {
            var languageList = document.getElementById("languageList");
            if (languageList.style.display === "block") {
                languageList.style.display = "none";
            } else {
                languageList.style.display = "block";
            }
        }
// Функция для периодического обновления активности
function startActivityUpdater() {
    // Обновляем сразу при загрузке
    updateActivity();
    
    // Затем каждые 5 минут
    setInterval(updateActivity, 5 * 60 * 1000);
}

async function updateActivity() {
    try {
        await fetch('/api/update_activity', {
            method: 'POST',
            credentials: 'same-origin'
        });
    } catch (error) {
        console.error('Error updating activity:', error);
    }
}

// Добавить в DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    startActivityUpdater();
    // остальная инициализация...
});