var wyysModal = (function(){
    var container = document.documentElement,
        popup = document.querySelector('.wyys-modal-animate'),
        currentState = null;
    container.className = container.className.replace(/\s+$/gi, '') + ' wyys-ready';
    // Deactivate on ESC
    function onDocumentKeyUp(event) {
        if(event.keyCode === 27) {
            deactivate();
        }
    }
    // Deactivate on click close
    function onDocumentClick(event) {
        if(event.target.className.indexOf('wyys-modal-head-close') > -1) {
            deactivate();
        }
    }
    function activate(state) {
        if(typeof window.addEventListener != "undefined") {
            document.addEventListener('keyup', onDocumentKeyUp, false);
            document.addEventListener('click', onDocumentClick, false);
            document.addEventListener('touchstart', onDocumentClick, false);
        }else{
            document.attachEvent('keyup', onDocumentKeyUp);
            document.attachEvent('click', onDocumentClick);
            document.attachEvent('touchstart', onDocumentClick);
        }
        removeClass(popup, currentState );
        addClass(popup, 'wyys-no-transition');
        addClass(popup, state );
        setTimeout( function() {
            removeClass(popup, 'wyys-no-transition');
            addClass(container, 'wyys-active');
        }, 0 );
        currentState = state;
    }
    function deactivate(popups) {
        if(typeof window.addEventListener != "undefined") {
            document.removeEventListener('keyup', onDocumentKeyUp, false);
            document.removeEventListener('click', onDocumentClick, false);
            document.removeEventListener('touchstart', onDocumentClick, false);
        } else{
            document.detachEvent('keyup', onDocumentKeyUp );
            document.detachEvent('click', onDocumentClick );
            document.detachEvent('touchstart', onDocumentClick );
        }
        removeClass(container, 'wyys-active' );
        removeClass(popups ? popups : popup, 'wyys-modal-animate')
    }
    function disableBlur() {
        addClass(document.documentElement, 'wyys-no-blur');
    }
    function addClass(element, name) {
        element.className = element.className.replace(/\s+$/gi, '') + ' ' + name;
    }
    function removeClass(element, name) {
        if(element) element.className = element.className.replace(name, '').replace(name, '').replace(name, '');
    }
    function show(selector){
        popup = document.querySelector(selector);
        addClass(popup, 'wyys-modal-animate');
        activate();
        return this;
    }
    function hide(selector) {
        popup = document.querySelector(selector);
        deactivate(popup);
    }
    return {
        activate: activate,
        deactivate: deactivate,
        disableBlur: disableBlur,
        show: show,
        hide: hide
    }
})();