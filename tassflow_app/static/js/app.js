document.addEventListener("DOMContentLoaded", () => {

    /* ================= ANIMACIÓN TARJETAS ================= */
    document.querySelectorAll(".card, .stat").forEach((card, index) => {
        card.style.opacity = "0";
        card.style.transform = "translateY(20px)";

        setTimeout(() => {
            card.style.transition = "all 0.5s ease";
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
        }, index * 120);
    });

    /* ================= CONTADORES ================= */
    document.querySelectorAll(".stat p").forEach(counter => {
        const target = Number(counter.innerText);
        let current = 0;
        const increment = Math.max(1, Math.ceil(target / 40));

        const update = () => {
            current += increment;
            if (current < target) {
                counter.innerText = current;
                requestAnimationFrame(update);
            } else {
                counter.innerText = target;
            }
        };
        update();
    });

    /* ================= CONFIRMAR ELIMINAR ================= */
    document.querySelectorAll(".btn-danger").forEach(btn => {
        btn.addEventListener("click", e => {
            if (!confirm("¿Seguro que deseas eliminar este usuario?")) {
                e.preventDefault();
            }
        });
    });

    /* ================= LIMITE USUARIOS ================= */
    const formAsignar = document.getElementById("formAsignar");
    if (formAsignar) {
        const checkboxes = formAsignar.querySelectorAll('input[name="usuarios"]');

        checkboxes.forEach(cb => {
            cb.addEventListener("change", () => {
                const seleccionados = formAsignar.querySelectorAll(
                    'input[name="usuarios"]:checked'
                );
                if (seleccionados.length > 2) {
                    cb.checked = false;
                    alert("Solo puedes asignar máximo 2 usuarios por tarea");
                }
            });
        });
    }

    /* ================= GRÁFICA ADMIN ================= */
    const canvas = document.getElementById("graficaTareas");
    if (canvas && window.chartData && !canvas.dataset.loaded) {
        canvas.dataset.loaded = "true";

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: ["Pendientes", "Completadas"],
                datasets: [{
                    data: [
                        window.chartData.pendientes,
                        window.chartData.completadas
                    ],
                    backgroundColor: ["#fbbf24", "#22c55e"],
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    /* ================= PROGRESO CIRCULAR ================= */
    document.querySelectorAll(".progreso-circulo").forEach(c => {
        c.style.setProperty("--valor", c.dataset.value || 0);
    });

    /* ================= CALENDARIO ================= */
    const calendarEl = document.getElementById("calendario");
    if (calendarEl && window.calendarData) {
        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: "dayGridMonth",
            locale: "es",
            height: "auto",
            headerToolbar: {
                left: "prev,next today",
                center: "title",
                right: ""
            },
            events: window.calendarData,
            eventClick: info => {
                alert(
                    "Tarea: " + info.event.title +
                    "\nFecha: " + info.event.start.toLocaleDateString()
                );
            }
        });
        calendar.render();
    }

});
