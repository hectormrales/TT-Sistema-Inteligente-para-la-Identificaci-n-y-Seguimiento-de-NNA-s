/**
 * Futuro Con Derechos — Script Principal del Sitio Institucional (2026)
 */

document.addEventListener('DOMContentLoaded', () => {
  // ── 1. Menú móvil interactivo ───────────────────────────
  const mobileBtn = document.getElementById('mobileMenuBtn');
  const navMenu = document.getElementById('navMenu');

  if (mobileBtn && navMenu) {
    mobileBtn.addEventListener('click', () => {
      navMenu.classList.toggle('active');
      const icon = mobileBtn.querySelector('i');
      if (icon) {
        if (navMenu.classList.contains('active')) {
          icon.classList.remove('fa-bars');
          icon.classList.add('fa-times');
        } else {
          icon.classList.remove('fa-times');
          icon.classList.add('fa-bars');
        }
      }
    });

    // Cerrar menú al hacer clic en un enlace
    navMenu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navMenu.classList.remove('active');
        const icon = mobileBtn.querySelector('i');
        if (icon) {
          icon.classList.remove('fa-times');
          icon.classList.add('fa-bars');
        }
      });
    });
  }

  // ── 2. Sombra en el header al hacer scroll ─────────────
  const header = document.getElementById('header');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  });

  // ── 3. Smooth scroll para anclas ───────────────────────
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        e.preventDefault();
        const headerOffset = 80;
        const elementPosition = targetElement.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });
      }
    });
  });
});

// ── 4. Manejador de envío del formulario de contacto ───────
function handleFormSubmit() {
  const nombre = document.getElementById('formNombre')?.value || '';
  const contacto = document.getElementById('formContacto')?.value || '';
  const mensaje = document.getElementById('formMensaje')?.value || '';
  const submitBtn = document.getElementById('btnSubmitForm');
  const successBox = document.getElementById('formSuccess');

  if (!nombre.trim() || !contacto.trim() || !mensaje.trim()) {
    alert('Por favor completa todos los campos del formulario.');
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Enviando...';
  }

  // Simulación de envío seguro (o integración con webhook de notificación)
  setTimeout(() => {
    if (submitBtn) {
      submitBtn.style.display = 'none';
    }
    if (successBox) {
      successBox.style.display = 'block';
    }
  }, 900);
}

