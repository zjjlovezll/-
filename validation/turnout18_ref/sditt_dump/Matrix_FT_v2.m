function [M_track,K_track,C_track] = Matrix_FT_v2(N_LSR, N_LDR, N_RSR, N_RDR, N_LCR, N_RCR, N_Rail, N_Sleeper, ...
          RailNodes_LSR, RailNodes_LDR, RailNodes_RSR, RailNodes_RDR, RailNodes_LCR, RailNodes_RCR, ...
          SleeperNodes_pos, SleeperNodes_pos_x, SleeperNodes_pos_y, SleeperNodes_count, Sleeper_Length, Sleeper_Mass, ...
          RailPadProp, CheckRailFastningProp, BallastProp, Ms, Es, I22_s)

Type_Rail = {'LSR', 'LDR', 'RSR', 'RDR', 'LCR', 'RCR'};
N_sum_rail = [0;
              N_LSR;
              N_LSR+N_LDR;
              N_LSR+N_LDR+N_RSR;
              N_LSR+N_LDR+N_RSR+N_RDR;
              N_LSR+N_LDR+N_RSR+N_RDR+N_LCR];
      
M_rail = zeros(4*N_Rail,4*N_Rail);
K_rail = zeros(4*N_Rail,4*N_Rail);
M_sleeper = zeros(2*N_Sleeper+length(SleeperNodes_count),2*N_Sleeper+length(SleeperNodes_count));
K_sleeper = zeros(2*N_Sleeper+length(SleeperNodes_count),2*N_Sleeper+length(SleeperNodes_count));
M_track = zeros(4*N_Rail+2*N_Sleeper+length(SleeperNodes_count),4*N_Rail+2*N_Sleeper+length(SleeperNodes_count));
K_track = zeros(4*N_Rail+2*N_Sleeper+length(SleeperNodes_count),4*N_Rail+2*N_Sleeper+length(SleeperNodes_count));
C_track = zeros(4*N_Rail+2*N_Sleeper+length(SleeperNodes_count),4*N_Rail+2*N_Sleeper+length(SleeperNodes_count));

%% ===================== 梁单元[M],[K]矩阵
for i = 1:1:6
%     if i==1
%         target = RailNodes_LSR; N_sum_temp = 0;
%     elseif i==2
%         target = RailNodes_LDR; N_sum_temp = N_LSR;
%     elseif i==3
%         target = RailNodes_RSR; N_sum_temp = N_LSR+N_LDR;
%     elseif i==4
%         target = RailNodes_RDR; N_sum_temp = N_LSR+N_LDR+N_RSR;
%     elseif i==5
%         target = RailNodes_LCR; N_sum_temp = N_LSR+N_LDR+N_RSR+N_RDR;
%     elseif i==6
%         target = RailNodes_RCR; N_sum_temp = N_LSR+N_LDR+N_RSR+N_RDR+N_LCR;
%     end
    
    eval(['target = RailNodes_',Type_Rail{i},';']);
    N_sum_temp = N_sum_rail(i);
    
    for j = 1:1:length(target)
        if ~isempty(target(j,1).Mass)
            a = target(j,1).Length;
            A = target(j,1).Mass * a / 420;
            M_sub = [156*A     22*A*a       54*A   -13*A*a
                      22*A*a    4*A*a^2     13*A*a  -3*A*a^2
                      54*A     13*A*a      156*A    -22*A*a
                     -13*A*a   -3*A*a^2    -22*A*a   4*A*a^2];
                        
            row_1 = 2*N_sum_temp+2*(j-1)+1;
            row_2 = 2*N_sum_temp+2*(j-1)+4;
            col_1 = row_1;
            col_2 = row_2;
            M_rail(row_1:row_2,col_1:col_2) = M_rail(row_1:row_2,col_1:col_2) + M_sub;
            M_rail(row_1+2*N_Rail:row_2+2*N_Rail,col_1+2*N_Rail:col_2+2*N_Rail) = ...
            M_rail(row_1+2*N_Rail:row_2+2*N_Rail,col_1+2*N_Rail:col_2+2*N_Rail) + M_sub;
        
        
            B_Ver = target(j,1).YoungModulus * target(j,1).I22 / a^3;
            B_Lat = target(j,1).YoungModulus * target(j,1).I11 / a^3;
            
            K_Ver_sub = [12*B_Ver      6*B_Ver*a     -12*B_Ver     6*B_Ver*a
                          6*B_Ver*a    4*B_Ver*a^2    -6*B_Ver*a   2*B_Ver*a^2
                        -12*B_Ver     -6*B_Ver*a      12*B_Ver    -6*B_Ver*a
                          6*B_Ver*a    2*B_Ver*a^2    -6*B_Ver*a   4*B_Ver*a^2];                      
            K_Lat_sub = [12*B_Lat      6*B_Lat*a     -12*B_Lat     6*B_Lat*a
                          6*B_Lat*a    4*B_Lat*a^2    -6*B_Lat*a   2*B_Lat*a^2
                        -12*B_Lat     -6*B_Lat*a      12*B_Lat    -6*B_Lat*a
                          6*B_Lat*a    2*B_Lat*a^2    -6*B_Lat*a   4*B_Lat*a^2];
                      
            K_rail(row_1:row_2,col_1:col_2) = K_rail(row_1:row_2,col_1:col_2) + K_Ver_sub;
            K_rail(row_1+2*N_Rail:row_2+2*N_Rail,col_1+2*N_Rail:col_2+2*N_Rail) = ...
            K_rail(row_1+2*N_Rail:row_2+2*N_Rail,col_1+2*N_Rail:col_2+2*N_Rail) + K_Lat_sub;
        end
    end
end

for i = 1:1:size(SleeperNodes_pos,1)
    for j = 1:1:SleeperNodes_count(i,1)-1
        a = Sleeper_Length(i,j);
        A = Ms * a / 420;
        M_sub = [156*A     22*A*a       54*A   -13*A*a
                  22*A*a    4*A*a^2     13*A*a  -3*A*a^2
                  54*A     13*A*a      156*A   -22*A*a
                 -13*A*a   -3*A*a^2    -22*A*a   4*A*a^2];
             
         row_1 = 2*(sum(SleeperNodes_count(1:i-1))+(j-1))+1;
         row_2 = 2*(sum(SleeperNodes_count(1:i-1))+(j-1))+4;
         col_1 = row_1;
         col_2 = row_2;
         M_sleeper(row_1:row_2,col_1:col_2) = M_sleeper(row_1:row_2,col_1:col_2) + M_sub;
         
         B_Ver = Es * I22_s / a^3;
         K_Ver_sub = [12*B_Ver      6*B_Ver*a     -12*B_Ver     6*B_Ver*a
                       6*B_Ver*a    4*B_Ver*a^2    -6*B_Ver*a   2*B_Ver*a^2
                     -12*B_Ver     -6*B_Ver*a      12*B_Ver    -6*B_Ver*a
                       6*B_Ver*a    2*B_Ver*a^2    -6*B_Ver*a   4*B_Ver*a^2];
         K_sleeper(row_1:row_2,col_1:col_2) = K_sleeper(row_1:row_2,col_1:col_2) + K_Ver_sub;
    end   
    
    row = 2*N_Sleeper + i;
    col = 2*N_Sleeper + i;
    M_sleeper(row,col) = M_sleeper(row,col) + Sleeper_Mass(i,1);
end

%% ===================== 合并 Rail 和 Sleeper 矩阵
M_track(1:4*N_Rail, 1:4*N_Rail) = M_rail;
M_track(4*N_Rail+1:end, 4*N_Rail+1:end) = M_sleeper;
K_track(1:4*N_Rail, 1:4*N_Rail) = K_rail;
K_track(4*N_Rail+1:end, 4*N_Rail+1:end) = K_sleeper;

%% ===================== 扣件约束[K],[C]矩阵
for i = 1:1:6
    eval(['target = RailNodes_',Type_Rail{i},';']);
    N_sum_temp = N_sum_rail(i);
    eval(['Sleeper_',Type_Rail{i},' = [];']);

    for j = 1:1:size(target,1)
        bools = 0;
        % Through Route
        if i == 3
            if (target(j,1).number>20000000+i*1e6 && target(j,1).number<20000105+i*1e6) || (target(j,1).number>25000000)
                bools = 1;
            end
        elseif i > 4
            if (target(j,1).number>20000000+(i+1)*1e6 && target(j,1).number<20000105+(i+1)*1e6)
                bools = 1;
            end
        else
            if (target(j,1).number>20000000+i*1e6 && target(j,1).number<20000105+i*1e6) || (target(j,1).number>28000000)
                bools = 1;
            end
        end
%         Diverging Route
%         if i == 2
%             if (target(j,1).number>20000000+i*1e6 && target(j,1).number<20000105+i*1e6) || (target(j,1).number>25000000)
%                 bools = 1;
%             end
%         elseif i > 4
%             if (target(j,1).number>20000000+(i+1)*1e6 && target(j,1).number<20000105+(i+1)*1e6)
%                 bools = 1;
%             end
%         else
%             if (target(j,1).number>20000000+i*1e6 && target(j,1).number<20000105+i*1e6) || (target(j,1).number>28000000)
%                 bools = 1;
%             end
%         end
        
        if bools == 1
            [~,m] = min(abs(SleeperNodes_pos_x(:,1) - target(j,1).location(1)));
            [~,n] = min(abs(SleeperNodes_pos_y(m,1:SleeperNodes_count(m,1)) - target(j,1).location(2)));
            MatPos_r_z   = 2*N_sum_temp+2*(j-1)+1;
            MatPos_s_z   = 2*(sum(SleeperNodes_count(1:m-1))+(n-1))+1+4*N_Rail;
            MatPos_r_y   = 2*N_sum_temp+2*(j-1)+1+2*N_Rail;
            MatPos_s_y   = 2*N_Sleeper+m+4*N_Rail;
            MatPos_r_pitch = 2*N_sum_temp+2*j;
            eval(['Sleeper_',Type_Rail{i},' = [Sleeper_',Type_Rail{i},'; target(j,1).number target(j,1).location MatPos_r_z MatPos_s_z MatPos_r_y MatPos_s_y MatPos_r_pitch];']);
        end
    end
    
end

for i = 1:1:6
    eval(['target = Sleeper_',Type_Rail{i},';']);
    if i <= 4
        PadProp = RailPadProp;
    else
        PadProp = CheckRailFastningProp;
    end
    
    for k = 1:1:size(target,1)
        MatPos_r_z = target(k,5);
        MatPos_s_z = target(k,6);
        MatPos_r_y = target(k,7);
        MatPos_s_y = target(k,8);
        MatPos_r_pitch = target(k,9);
        
        K_track(MatPos_r_z,MatPos_r_z) = K_track(MatPos_r_z,MatPos_r_z)+PadProp.kz_pad;
        K_track(MatPos_r_z,MatPos_s_z) = K_track(MatPos_r_z,MatPos_s_z)-PadProp.kz_pad;
        K_track(MatPos_s_z,MatPos_r_z) = K_track(MatPos_s_z,MatPos_r_z)-PadProp.kz_pad;
        K_track(MatPos_s_z,MatPos_s_z) = K_track(MatPos_s_z,MatPos_s_z)+PadProp.kz_pad;
        
        K_track(MatPos_r_y,MatPos_r_y) = K_track(MatPos_r_y,MatPos_r_y)+PadProp.ky_pad;
        K_track(MatPos_r_y,MatPos_s_y) = K_track(MatPos_r_y,MatPos_s_y)-PadProp.ky_pad;
        K_track(MatPos_s_y,MatPos_r_y) = K_track(MatPos_s_y,MatPos_r_y)-PadProp.ky_pad;
        K_track(MatPos_s_y,MatPos_s_y) = K_track(MatPos_s_y,MatPos_s_y)+PadProp.ky_pad;
        
        C_track(MatPos_r_z,MatPos_r_z) = C_track(MatPos_r_z,MatPos_r_z)+PadProp.dz_pad;
        C_track(MatPos_r_z,MatPos_s_z) = C_track(MatPos_r_z,MatPos_s_z)-PadProp.dz_pad;
        C_track(MatPos_s_z,MatPos_r_z) = C_track(MatPos_s_z,MatPos_r_z)-PadProp.dz_pad;
        C_track(MatPos_s_z,MatPos_s_z) = C_track(MatPos_s_z,MatPos_s_z)+PadProp.dz_pad;
        
        C_track(MatPos_r_y,MatPos_r_y) = C_track(MatPos_r_y,MatPos_r_y)+PadProp.dy_pad;
        C_track(MatPos_r_y,MatPos_s_y) = C_track(MatPos_r_y,MatPos_s_y)-PadProp.dy_pad;
        C_track(MatPos_s_y,MatPos_r_y) = C_track(MatPos_s_y,MatPos_r_y)-PadProp.dy_pad;
        C_track(MatPos_s_y,MatPos_s_y) = C_track(MatPos_s_y,MatPos_s_y)+PadProp.dy_pad;        
        
        K_track(MatPos_r_pitch,MatPos_r_pitch) = K_track(MatPos_r_pitch,MatPos_r_pitch)+PadProp.kyrot_pad;
        C_track(MatPos_r_pitch,MatPos_r_pitch) = C_track(MatPos_r_pitch,MatPos_r_pitch)+PadProp.dyrot_pad;
    end
    
end

% figure(1); clf
% temp = diff(Sleeper_RSR(:,5));
% temp = Sleeper_RSR(:,7)-Sleeper_RSR(:,5);
% plot(1:1:length(temp),temp)

%% ===================== 道床约束[K],[C]矩阵
for i = 1:1:length(SleeperNodes_count)
    for j = 1:1:SleeperNodes_count(i,1)
        if j == 1
            dL = SleeperNodes_pos_y(i,j+1)-SleeperNodes_pos_y(i,j);
        elseif j == SleeperNodes_count(i,1)
            dL = SleeperNodes_pos_y(i,j)-SleeperNodes_pos_y(i,j-1);
        else
            dL = SleeperNodes_pos_y(i,j+1)-SleeperNodes_pos_y(i,j-1);
        end
        
        kz_ballast_elem = BallastProp.kz_ballast*dL/2;
        ky_ballast_elem = BallastProp.ky_ballast*dL/2;
        dz_ballast_elem = BallastProp.dz_ballast*dL/2;
        dy_ballast_elem = BallastProp.dy_ballast*dL/2;

        MatPos_s_z = 4*N_Rail+2*(sum(SleeperNodes_count(1:i-1))+(j-1))+1;
        MatPos_s_y = 4*N_Rail+2*N_Sleeper+i;
        
        K_track(MatPos_s_z,MatPos_s_z) = K_track(MatPos_s_z,MatPos_s_z) + kz_ballast_elem;
        K_track(MatPos_s_y,MatPos_s_y) = K_track(MatPos_s_y,MatPos_s_y) + ky_ballast_elem;
        C_track(MatPos_s_z,MatPos_s_z) = C_track(MatPos_s_z,MatPos_s_z) + dz_ballast_elem;
        C_track(MatPos_s_y,MatPos_s_y) = C_track(MatPos_s_y,MatPos_s_y) + dy_ballast_elem;
        
    end
end

