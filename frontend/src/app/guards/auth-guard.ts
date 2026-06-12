import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router'; 
import { AuthService } from '../services/auth-service';

export const authGuard: CanActivateFn = async (route, state) => {

  const authService = inject(AuthService); 
  const router = inject(Router); 

  const claims = await authService.getUser(); 

  if (!claims) {
    return router.parseUrl('/auth');
  }

  try {
    // Check if user has a profile in the supabase database
    const { data, error } = await authService.supabaseClient
      .from('profiles')
      .select('id')
      .eq('auth_id', claims.id)
      .maybeSingle();

    const hasProfile = !!data;
    const isFirstLoginPath = state.url.startsWith('/first-login');

    if (hasProfile) {
      if (isFirstLoginPath) {
        return router.parseUrl('/internal/marketplace');
      }
      return true;
    } else {
      if (isFirstLoginPath) {
        return true;
      }
      return router.parseUrl('/first-login');
    }
  } catch (err) {
    console.error('Error in authGuard check:', err);
    // If query fails, fall back to default behavior to avoid locking users out
    return true;
  }
};
