// BYOD Security System - Main JavaScript File
// Theme management, interactive behaviors, modal system, and form validation

(function() {
    'use strict';

    // Theme Management
    const ThemeManager = {
        init() {
            this.loadTheme();
            this.bindEvents();
        },

        loadTheme() {
            const savedTheme = localStorage.getItem('theme');
            const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const theme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
            
            this.setTheme(theme);
        },

        setTheme(theme) {
            const html = document.documentElement;
            const themeToggle = document.getElementById('theme-toggle');
            
            if (theme === 'dark') {
                html.classList.add('dark');
                if (themeToggle) {
                    themeToggle.innerHTML = `
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>
                        </svg>
                    `;
                }
            } else {
                html.classList.remove('dark');
                if (themeToggle) {
                    themeToggle.innerHTML = `
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>
                        </svg>
                    `;
                }
            }
            
            localStorage.setItem('theme', theme);
        },

        toggle() {
            const currentTheme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            this.setTheme(newTheme);
        },

        bindEvents() {
            const themeToggle = document.getElementById('theme-toggle');
            if (themeToggle) {
                themeToggle.addEventListener('click', () => this.toggle());
            }
        }
    };

    // Sidebar Management
    const SidebarManager = {
        init() {
            this.bindEvents();
            this.handleResize();
        },

        toggle() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            
            if (sidebar && overlay) {
                const isOpen = !sidebar.classList.contains('-translate-x-full');
                
                if (isOpen) {
                    sidebar.classList.add('-translate-x-full');
                    overlay.classList.add('hidden');
                } else {
                    sidebar.classList.remove('-translate-x-full');
                    overlay.classList.remove('hidden');
                }
            }
        },

        close() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            
            if (sidebar && overlay) {
                sidebar.classList.add('-translate-x-full');
                overlay.classList.add('hidden');
            }
        },

        handleResize() {
            window.addEventListener('resize', () => {
                if (window.innerWidth >= 1024) {
                    this.close();
                }
            });
        },

        bindEvents() {
            const menuButton = document.getElementById('menu-button');
            const overlay = document.getElementById('sidebar-overlay');
            
            if (menuButton) {
                menuButton.addEventListener('click', () => this.toggle());
            }
            
            if (overlay) {
                overlay.addEventListener('click', () => this.close());
            }
        }
    };

    // Modal System
    const ModalManager = {
        init() {
            this.bindEvents();
        },

        open(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
                document.body.style.overflow = 'hidden';
                
                // Focus trap
                const focusableElements = modal.querySelectorAll(
                    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
                );
                if (focusableElements.length > 0) {
                    focusableElements[0].focus();
                }
            }
        },

        close(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
                document.body.style.overflow = '';
            }
        },

        closeAll() {
            const modals = document.querySelectorAll('[id$="-modal"]');
            modals.forEach(modal => {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            });
            document.body.style.overflow = '';
        },

        bindEvents() {
            // Open modal buttons
            document.addEventListener('click', (e) => {
                if (e.target.matches('[data-modal-open]')) {
                    const modalId = e.target.getAttribute('data-modal-open');
                    this.open(modalId);
                }
            });

            // Close modal buttons
            document.addEventListener('click', (e) => {
                if (e.target.matches('[data-modal-close]')) {
                    const modalId = e.target.getAttribute('data-modal-close');
                    this.close(modalId);
                }
            });

            // Close on backdrop click
            document.addEventListener('click', (e) => {
                if (e.target.matches('.modal-backdrop')) {
                    this.closeAll();
                }
            });

            // Close on escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this.closeAll();
                }
            });
        }
    };

    // Form Validation
    const FormValidator = {
        init() {
            this.bindEvents();
        },

        validateField(field) {
            const value = field.value.trim();
            const type = field.type;
            const required = field.hasAttribute('required');
            let isValid = true;
            let message = '';

            // Clear previous validation
            this.clearFieldValidation(field);

            // Required validation
            if (required && !value) {
                isValid = false;
                message = 'This field is required.';
            }

            // Type-specific validation
            if (value && isValid) {
                switch (type) {
                    case 'email':
                        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                        if (!emailRegex.test(value)) {
                            isValid = false;
                            message = 'Please enter a valid email address.';
                        }
                        break;
                    
                    case 'password':
                        if (value.length < 8) {
                            isValid = false;
                            message = 'Password must be at least 8 characters long.';
                        }
                        break;
                }
            }

            // Custom validation patterns
            const pattern = field.getAttribute('pattern');
            if (value && pattern && isValid) {
                const regex = new RegExp(pattern);
                if (!regex.test(value)) {
                    isValid = false;
                    message = field.getAttribute('data-pattern-message') || 'Invalid format.';
                }
            }

            // MAC address validation
            if (field.name === 'mac_address' && value && isValid) {
                const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
                if (!macRegex.test(value)) {
                    isValid = false;
                    message = 'Please enter a valid MAC address (e.g., 00:1B:44:11:3A:B7).';
                }
            }

            this.setFieldValidation(field, isValid, message);
            return isValid;
        },

        setFieldValidation(field, isValid, message) {
            const container = field.closest('.form-group') || field.parentElement;
            
            if (isValid) {
                field.classList.remove('form-input-error');
                field.classList.add('form-input-success');
            } else {
                field.classList.remove('form-input-success');
                field.classList.add('form-input-error');
                
                // Show error message
                let errorElement = container.querySelector('.form-error');
                if (!errorElement) {
                    errorElement = document.createElement('div');
                    errorElement.className = 'form-error mt-1';
                    container.appendChild(errorElement);
                }
                errorElement.textContent = message;
            }
        },

        clearFieldValidation(field) {
            const container = field.closest('.form-group') || field.parentElement;
            field.classList.remove('form-input-error', 'form-input-success');
            
            const errorElement = container.querySelector('.form-error');
            if (errorElement) {
                errorElement.remove();
            }
        },

        validateForm(form) {
            const fields = form.querySelectorAll('input, select, textarea');
            let isFormValid = true;

            fields.forEach(field => {
                if (!this.validateField(field)) {
                    isFormValid = false;
                }
            });

            return isFormValid;
        },

        bindEvents() {
            // Real-time validation on blur
            document.addEventListener('blur', (e) => {
                if (e.target.matches('input, select, textarea')) {
                    this.validateField(e.target);
                }
            }, true);

            // Form submission validation
            document.addEventListener('submit', (e) => {
                const form = e.target;
                if (form.matches('form[data-validate]')) {
                    if (!this.validateForm(form)) {
                        e.preventDefault();
                        
                        // Focus first invalid field
                        const firstInvalid = form.querySelector('.form-input-error');
                        if (firstInvalid) {
                            firstInvalid.focus();
                        }
                    }
                }
            });
        }
    };

    // Utility Functions
    const Utils = {
        // Show loading state
        showLoading(element, text = 'Loading...') {
            const originalContent = element.innerHTML;
            element.setAttribute('data-original-content', originalContent);
            element.innerHTML = `
                <span class="spinner mr-2"></span>
                ${text}
            `;
            element.disabled = true;
        },

        // Hide loading state
        hideLoading(element) {
            const originalContent = element.getAttribute('data-original-content');
            if (originalContent) {
                element.innerHTML = originalContent;
                element.removeAttribute('data-original-content');
            }
            element.disabled = false;
        },

        // Show notification with enhanced features
        showNotification(message, type = 'info', duration = 5000, persistent = false) {
            const notification = document.createElement('div');
            const notificationId = 'notification-' + Date.now();
            notification.id = notificationId;
            notification.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm slide-in-right ${this.getNotificationClasses(type)}`;
            
            // Add icon based on type
            const icon = this.getNotificationIcon(type);
            
            notification.innerHTML = `
                <div class="flex items-start">
                    <div class="flex-shrink-0">
                        ${icon}
                    </div>
                    <div class="ml-3 flex-1">
                        <p class="text-sm font-medium">${message}</p>
                    </div>
                    <button onclick="Utils.dismissNotification('${notificationId}')" class="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                ${!persistent && type !== 'error' ? '<div class="notification-progress absolute bottom-0 left-0 h-1 bg-current opacity-30"></div>' : ''}
            `;

            // Position multiple notifications
            const existingNotifications = document.querySelectorAll('[id^="notification-"]');
            if (existingNotifications.length > 0) {
                const topOffset = 16 + (existingNotifications.length * 80);
                notification.style.top = `${topOffset}px`;
            }

            document.body.appendChild(notification);

            // Add progress bar animation for auto-dismissing notifications
            if (!persistent && type !== 'error') {
                const progressBar = notification.querySelector('.notification-progress');
                if (progressBar) {
                    progressBar.style.width = '100%';
                    progressBar.style.transition = `width ${duration}ms linear`;
                    setTimeout(() => {
                        progressBar.style.width = '0%';
                    }, 50);
                }
            }

            // Auto remove after duration (except for errors and persistent notifications)
            if (!persistent && type !== 'error') {
                setTimeout(() => {
                    this.dismissNotification(notificationId);
                }, duration);
            }

            return notificationId;
        },

        // Dismiss notification with animation
        dismissNotification(notificationId) {
            const notification = document.getElementById(notificationId);
            if (notification) {
                notification.style.transition = 'all 0.3s ease-out';
                notification.style.opacity = '0';
                notification.style.transform = 'translateX(100%)';
                
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                        // Reposition remaining notifications
                        this.repositionNotifications();
                    }
                }, 300);
            }
        },

        // Reposition notifications after one is dismissed
        repositionNotifications() {
            const notifications = document.querySelectorAll('[id^="notification-"]');
            notifications.forEach((notification, index) => {
                const topOffset = 16 + (index * 80);
                notification.style.top = `${topOffset}px`;
                notification.style.transition = 'top 0.3s ease-out';
            });
        },

        // Get notification icon based on type
        getNotificationIcon(type) {
            const icons = {
                success: `<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>`,
                error: `<svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>`,
                warning: `<svg class="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z"></path>
                </svg>`,
                info: `<svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>`
            };
            return icons[type] || icons.info;
        },

        getNotificationClasses(type) {
            const classes = {
                success: 'bg-green-50 text-green-800 border border-green-200',
                error: 'bg-red-50 text-red-800 border border-red-200',
                warning: 'bg-yellow-50 text-yellow-800 border border-yellow-200',
                info: 'bg-blue-50 text-blue-800 border border-blue-200'
            };
            return classes[type] || classes.info;
        },

        // Format MAC address
        formatMacAddress(input) {
            let value = input.value.replace(/[^0-9A-Fa-f]/g, '');
            value = value.match(/.{1,2}/g)?.join(':') || value;
            if (value.length > 17) value = value.substring(0, 17);
            input.value = value.toUpperCase();
        }
    };

    // Global functions for template use
    window.toggleSidebar = () => SidebarManager.toggle();
    window.openModal = (modalId) => ModalManager.open(modalId);
    window.closeModal = (modalId) => ModalManager.close(modalId);
    window.showNotification = (message, type, duration, persistent) => Utils.showNotification(message, type, duration, persistent);
    window.dismissNotification = (notificationId) => Utils.dismissNotification(notificationId);
    window.formatMacAddress = (input) => Utils.formatMacAddress(input);
    window.toggleMessageAutoDismiss = () => toggleMessageAutoDismiss();

    // Performance optimizations
    const PerformanceOptimizer = {
        init() {
            this.setupLazyLoading();
            this.setupIntersectionObserver();
            this.debounceScrollEvents();
        },

        setupLazyLoading() {
            // Lazy load images with data-src attribute
            const lazyImages = document.querySelectorAll('img[data-src]');
            if ('IntersectionObserver' in window) {
                const imageObserver = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            img.classList.remove('lazy');
                            imageObserver.unobserve(img);
                        }
                    });
                });

                lazyImages.forEach(img => imageObserver.observe(img));
            } else {
                // Fallback for older browsers
                lazyImages.forEach(img => {
                    img.src = img.dataset.src;
                });
            }
        },

        setupIntersectionObserver() {
            // Animate elements when they come into view
            if ('IntersectionObserver' in window) {
                const animateObserver = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('animate-in');
                            animateObserver.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.1 });

                document.querySelectorAll('.animate-on-scroll').forEach(el => {
                    animateObserver.observe(el);
                });
            }
        },

        debounceScrollEvents() {
            let scrollTimeout;
            window.addEventListener('scroll', () => {
                if (scrollTimeout) {
                    clearTimeout(scrollTimeout);
                }
                scrollTimeout = setTimeout(() => {
                    // Handle scroll events here if needed
                }, 100);
            }, { passive: true });
        },

        // Debounce function for performance
        debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    };

    // Initialize everything when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        ThemeManager.init();
        SidebarManager.init();
        ModalManager.init();
        FormValidator.init();
        PerformanceOptimizer.init();
        
        // Auto-format MAC address inputs with debouncing
        const debouncedMacFormat = PerformanceOptimizer.debounce((input) => {
            Utils.formatMacAddress(input);
        }, 300);
        
        document.addEventListener('input', (e) => {
            if (e.target.name === 'mac_address') {
                debouncedMacFormat(e.target);
            }
        });
        
        // Add loading states to forms
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.matches('form')) {
                const submitButton = form.querySelector('button[type="submit"]');
                if (submitButton && !submitButton.disabled) {
                    Utils.showLoading(submitButton, 'Processing...');
                }
            }
        });
        
        console.log('BYOD Security System initialized with performance optimizations');
    });

})();