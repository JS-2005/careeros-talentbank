import { Component } from '@angular/core';
import { AuthService } from '../services/auth-service';

@Component({
  selector: 'app-root',
  templateUrl: './auth.html',
  styleUrl: './auth.css',
})

export class Auth {
  constructor(private authService: AuthService) {}

  async login() {
    try {
      await this.authService.signInWithGoogle(); 
    } catch(error) {
      alert('Login failed: '+error); 
    }
  }; 

  async signOut() {
    try{
      await this.authService.signOut(); 
    } catch(error){
      alert('Sign Out Error: '+error); 
    }
  }
}
