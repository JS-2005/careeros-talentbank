import { Component } from '@angular/core';
import { AuthService } from '../services/auth-service';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-root',
  templateUrl: './auth.html',
  styleUrl: './auth.css',
})

export class Auth {
  isProduction = environment.production;

  constructor(private authService: AuthService, private router: Router) {}

  async login() {
    try {
      await this.authService.signInWithGoogle(); 
    } catch(error) {
      alert('Login failed: '+error); 
    }
  }; 

  async devLogin() {
    try {
      this.authService.devSignIn();
      this.router.navigate(['/internal']);
    } catch(error) {
      alert('Dev Login failed: '+error); 
    }
  }

  async signOut() {
    try{
      await this.authService.signOut(); 
    } catch(error){
      alert('Sign Out Error: '+error); 
    }
  }
}
