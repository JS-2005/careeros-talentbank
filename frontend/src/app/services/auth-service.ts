import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private supabase: SupabaseClient;

  constructor() {
    this.supabase = createClient(environment.supabaseUrl, environment.supabaseKey);
  }

  get supabaseClient(): SupabaseClient {
    return this.supabase;
  }

  private currentUser: any = null;

  async signInWithGoogle() {
    this.currentUser = null;
    const { data, error } = await this.supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/internal`
      }
    });
    
    if (error) throw error;
    
    return data;
  }

  devSignIn() {
    this.currentUser = {
      id: '747e12b2-4a5d-47ee-98d9-fa71a714b9ad',
      email: 'tansx1007@gmail.com',
      user_metadata: {
        full_name: 'SX Tan'
      }
    };
    const mockSession = {
      access_token: 'dev-token',
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'dev-refresh',
      user: this.currentUser
    };
    localStorage.setItem('sb-hoswkhsznqgdtaxmrpka-auth-token', JSON.stringify(mockSession));
    return this.currentUser;
  }

  async getUser() {
    if (this.currentUser) {
      return this.currentUser;
    }
    const stored = localStorage.getItem('sb-hoswkhsznqgdtaxmrpka-auth-token');
    if (stored) {
      try {
        const session = JSON.parse(stored);
        if (session.access_token === 'dev-token') {
          this.currentUser = session.user;
          return this.currentUser;
        }
      } catch (e) {}
    }
    const { data, error } = await this.supabase.auth.getUser(); 

    if(error || !data?.user) return null; 

    this.currentUser = data.user;
    return data.user; 
  }
  
  async signOut() {
    this.currentUser = null;
    localStorage.removeItem('sb-hoswkhsznqgdtaxmrpka-auth-token');
    try {
      await this.supabase.auth.signOut(); 
    } catch (e) {}
  }
  
}