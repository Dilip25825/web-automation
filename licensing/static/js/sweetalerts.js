// 1. Delete Confirmation Function
function confirmDelete(event, element, recordId) {
    event.preventDefault(); // Click ka default behavior rokna

    var targetUrl = element.getAttribute('data-url');

    Swal.fire({
        title: 'Kya aap sure hain?',
        text: "Record ID: " + recordId + " permanent delete ho jayega! Yeh action undo nahi hoga.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Haan, delete karein!',
        cancelButtonText: 'Cancel'
    }).then((result) => {
        if (result.isConfirmed) {
            window.location.href = targetUrl; // Safety Check ke baad redirection
        }
    });
}

// 2. Global Django Messages To SweetAlert Toast Converter
document.addEventListener("DOMContentLoaded", function() {
    const msgElements = document.querySelectorAll('#django-messages-container .django-msg');
    
    msgElements.forEach(function(element) {
        let msgType = element.getAttribute('data-tags');
        let msgText = element.innerText;
        let alertTitle = "Notification";

        // Error Handling: Sahi status check aur icon mapping
        if (msgType === 'error' || msgType === 'danger') {
            msgType = 'error';
            alertTitle = 'Error!';
        } else if (msgType === 'success') {
            msgType = 'success';
            alertTitle = 'Success!';
        } else if (msgType === 'warning') {
            msgType = 'warning';
            alertTitle = 'Warning!';
        } else {
            msgType = 'info';
            alertTitle = 'Info';
        }

        Swal.fire({
            title: alertTitle,
            text: msgText,
            icon: msgType,
            timer: 4000, 
            showConfirmButton: false,
            position: 'top-end', 
            toast: true 
        });
    });
});