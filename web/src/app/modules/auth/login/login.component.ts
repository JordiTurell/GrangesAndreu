import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
  standalone: true,
  imports: [FormsModule]
})
export class LoginComponent {
  credentials = {
    email: '',
    password: ''
  };

  rememberMe = false;
  loading = false;

  constructor(private router: Router) {}

  onSubmit() {
    this.loading = true;

    // Simulación de llamada a la API
    setTimeout(() => {
      this.loading = false;
      // Redirigir al dashboard después del login exitoso
      this.router.navigate(['/dashboard']);
    }, 1500);
  }
}