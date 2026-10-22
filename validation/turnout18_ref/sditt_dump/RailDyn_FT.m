%% 计算车轮下钢轨的位移、速度、加速度
function [Dis_Rail, Vel_Rail, Acc_Rail] = RailDyn_FT(j1, Distance_Vehicle, Nw, Zwy, Zsd, Zjsd, ...
          Type_Rail, N_Rail, N_sum_rail, RailNodes_pos, RailNodes_LSR, RailNodes_LDR, RailNodes_RSR, RailNodes_RDR, RailNodes_LCR, RailNodes_RCR)

Dis_Rail = zeros(16,3);                         % 存放本次计算八个车轮（行）下钢轨 X、Y、Z 方向位移（列） m
Vel_Rail = zeros(16,3);                         % 绝对坐标下，左、右车轮（行）下钢轨上接触点 X、Y、Z 方向（列）速度 m/s
Acc_Rail = zeros(16,3);                         % 存放本次计算八个车轮（行）下钢轨 X、Y、Z 方向（列）加速度 m/s^2

for i1 = 1:1:Nw         %%% 轮对数
    for i2 = 1:1:4      %%% 集总质量块数目
        i_wheel = 4*(i1-1)+i2;
        Mileage  = j1 - Distance_Vehicle(i1);
        % Through Route
        if i2 == 2
            kk = 5;
        else
            kk = i2;
        end
%         % Diverging Route
%         if i2 == 3
%             kk = 6;
%         else
%             kk = i2;
%         end
        eval(['RailNodes_pos_temp = RailNodes_pos.',Type_Rail{kk},';']);
        eval(['RailNodes_temp = RailNodes_',Type_Rail{kk},';']);
        N_sum_temp = N_sum_rail(kk);
        m = find(Mileage-RailNodes_pos_temp(:,1)>=0, 1, 'last');
        if ~isempty(m) && m<size(RailNodes_pos_temp,1)
            row_z = 2*N_sum_temp+2*(m-1)+1;
            row_y = 2*N_sum_temp+2*(m-1)+1+2*N_Rail;
            x = Mileage - RailNodes_pos_temp(m,1);
            a = RailNodes_temp(m,1).Length;
            ShapeFunction = [1-3*(x/a)^2+2*(x/a)^3, x*(1-2*x/a+(x/a)^2), (x/a)^2*(3-2*x/a), x*((x/a)^2-x/a)];
            Dis_Rail(i_wheel,2) = ShapeFunction * Zwy(row_y:row_y+3,4);     % 钢轨横向位移
            Dis_Rail(i_wheel,3) = ShapeFunction * Zwy(row_z:row_z+3,4);     % 钢轨垂向位移
            Vel_Rail(i_wheel,2) = ShapeFunction * Zsd(row_y:row_y+3,4);     % 钢轨横向速度
            Vel_Rail(i_wheel,3) = ShapeFunction * Zsd(row_z:row_z+3,4);     % 钢轨垂向速度
            Acc_Rail(i_wheel,2) = ShapeFunction * Zjsd(row_y:row_y+3,4);    % 钢轨横向加速度
            Acc_Rail(i_wheel,3) = ShapeFunction * Zjsd(row_z:row_z+3,4);    % 钢轨垂向加速度
        end
    end
end
