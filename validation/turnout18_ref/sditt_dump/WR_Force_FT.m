%% 轮轨力对柔性轨道（有限单元法）系统做功
function Pxt = WR_Force_FT(Pxt, Zwy, j1, xlcs, N_track, N_sum_rail, N_Rail, NM, Nw, Pjcc, Pjch, Prhxf, Expression_WS, Type_Side, ...
                           Con_FF,  Con_FR,  Con_RF,  Con_RR, Mileage_sum_Stock, Mileage_sum_Switch, Mileage_sum_Check, Distance_Vehicle, ...
                           Type_Rail, RailNodes_pos, RailNodes_LSR, RailNodes_LDR, RailNodes_RSR, RailNodes_RDR, RailNodes_LCR, RailNodes_RCR)
 
for i1 = 1:1:Nw             %%% 轮对数 1-4
    if xlcs <= 3 && isempty(Con_FF)
        for i2 = 1:3:4      %%% 从转辙器区启动：接触对数 1、4
%        for i2 = 2:2:4      %%% 从辙叉区启动：接触对数 2、4
            wheelside = fix((i2+1)/2);  %%% Left->1, Right->2
            i_contact_normal = 4*(i1-1)+i2;
            i_contact_creep = 16*(i1-1)+4*(i2-1);
            F_Ver = Pjcc(i_contact_normal,1) - Prhxf(i_contact_creep+4,1);
            F_Lat = Pjch(i_contact_normal,1)*(-1)^(wheelside) - Prhxf(i_contact_creep+3,1);
            Mileage  = j1 - Distance_Vehicle(i1);
            eval(['RailNodes_pos_temp = RailNodes_pos.',Type_Rail{i2},';']);
            eval(['RailNodes_temp = RailNodes_',Type_Rail{i2},';']);
            N_sum_temp = N_sum_rail(i2);
            Pxt = Cal_ShapeFunction_P(Pxt, Mileage, RailNodes_pos_temp, RailNodes_temp, N_sum_temp, N_Rail, F_Ver, F_Lat);
        end
    else
        eval(['Con_str = Con_',Expression_WS{i1},';']);
        for wheelside = 1:1:2
            eval(['Normal_Force = Con_str.Normal_Force_',Type_Side{wheelside},';']);
            eval(['Con_wheel_2 = Con_str.Con_wheel_',Type_Side{wheelside},'_2;']);
            eval(['Prhxf_temp = Con_str.Prhxf_',Type_Side{wheelside},';']);
            for k = 1:1:length(Normal_Force)
                % 判断接触点位置
                % Through Route
                if wheelside == 1
                    if ~isempty(Con_str.profile_r_L2) && Con_str.Con_rail_L_1(k,1) > min(Con_str.profile_r_L2(:,1))
                        i2 = 5; kk = -1;	%% 接触点在直股护轨上，LCR
                    else
                        i2 = 1; kk = 1;     %% 接触点在直基本轨上，LSR
                    end
                elseif wheelside == 2
                    if ~isempty(Con_str.profile_r_R1) && Con_str.Con_rail_R_1(k,1) < max(Con_str.profile_r_R1(:,1))
                        i2 = 3; kk = 1;     %% 与直尖轨接触，RSR
                    else
                        i2 = 4; kk = 1;     %% 与曲基本轨接触，RDR
                    end
                end
                % Diverging Route
%                 if wheelside == 1
% %                     if Con_str.Mileage > Mileage_sum_Stock(end,1)
% %                         i2 = 2; kk = 1;     %% 直基本轨里程范围之外，Switch rail / Crossing rail
% %                     elseif Con_str.Mileage < Mileage_sum_Switch(1,1)
% %                         i2 = 1; kk = 1;     %% 曲尖轨里程范围之外，Stock rail
% %                     elseif Con_str.Con_rail_L_1(k,1) > min(Con_str.profile_r_L2(:,1))
% %                         i2 = 2; kk = 1;     %% 接触点在曲尖轨/辙叉上，Switch rail / Crossing rail
% %                     else
% %                         i2 = 1; kk = 1;     %% 接触点在直基本轨上，Stock rail
% %                     end
%                     if ~isempty(Con_str.profile_r_L2) && Con_str.Con_rail_L_1(k,1) > min(Con_str.profile_r_L2(:,1))
%                         i2 = 2; kk = 1;     %% 接触点在曲尖轨/辙叉上，LDR
%                     else
%                         i2 = 1; kk = 1;     %% 接触点在直基本轨上，LSR
%                     end
%                 elseif wheelside == 2
% %                     if Con_str.Mileage < Mileage_sum_Check(1,1) || Con_str.Mileage > Mileage_sum_Check(end,1)
% %                         i2 = 4; kk = 1;     %% 护轨里程范围之外，Opposite stock rail
% %                     elseif Con_str.Con_rail_R_1(k,1) > max(Con_str.profile_r_R1(:,1))
% %                         i2 = 4; kk = 1;     %% 护轨里程范围内，但不接触护轨，Opposite stock rail
% %                     else
% %                         i2 = 6; kk = -1;    %% 与护轨接触，Check rail
% %                     end
%                     if ~isempty(Con_str.profile_r_R1) && Con_str.Con_rail_R_1(k,1) < max(Con_str.profile_r_R1(:,1))
%                         i2 = 6; kk = -1;    %% 与护轨接触，RCR
%                     else
%                         i2 = 4; kk = 1;     %% 与曲基本轨接触，RDR
%                     end
%                 end
                Pjcc_temp = Normal_Force(k).*cos(Con_wheel_2(k,6)+kk*(-1)^(wheelside+1)*Zwy(N_track+NM*Nw+5*(i1-1)+3,4));
                Pjch_temp = kk * Normal_Force(k).*sin(Con_wheel_2(k,6)+kk*(-1)^(wheelside+1)*Zwy(N_track+NM*Nw+5*(i1-1)+3,4));
                F_Ver = Pjcc_temp - Prhxf_temp(k,3);
                F_Lat = Pjch_temp*(-1)^(wheelside) - Prhxf_temp(k,2);
                Mileage  = j1 - Distance_Vehicle(i1);
                eval(['RailNodes_pos_temp = RailNodes_pos.',Type_Rail{i2},';']);
                eval(['RailNodes_temp = RailNodes_',Type_Rail{i2},';']);
                N_sum_temp = N_sum_rail(i2);
                Pxt = Cal_ShapeFunction_P(Pxt, Mileage, RailNodes_pos_temp, RailNodes_temp, N_sum_temp, N_Rail, F_Ver, F_Lat);
            end
        end
    end
end